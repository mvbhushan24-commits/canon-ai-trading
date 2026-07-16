"""Market structure detection orchestrator."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_data import NormalizedCandle
from backend.engines.market_structure.bos import BOSDetector
from backend.engines.market_structure.choch import CHoCHDetector
from backend.engines.market_structure.config import MarketStructureConfig
from backend.engines.market_structure.schemas import (
    BOSEvent,
    CHoCHEvent,
    MarketStructure,
    StructureEvent,
    StructureEventKind,
    StructureState,
    SwingPoint,
    TrendDirection,
)
from backend.engines.market_structure.swings import SwingDetector
from backend.engines.market_structure.trend import TrendAnalyzer


class StructureDetector:
    """Orchestrate swing, trend, BOS, and CHoCH detection."""

    def __init__(
        self,
        config: MarketStructureConfig,
        swing_detector: SwingDetector | None = None,
        trend_analyzer: TrendAnalyzer | None = None,
        bos_detector: BOSDetector | None = None,
        choch_detector: CHoCHDetector | None = None,
    ) -> None:
        self._config = config
        self._swing_detector = swing_detector or SwingDetector()
        self._trend_analyzer = trend_analyzer or TrendAnalyzer()
        self._bos_detector = bos_detector or BOSDetector()
        self._choch_detector = choch_detector or CHoCHDetector()

    def detect(
        self,
        candles: list[NormalizedCandle],
        *,
        prior_state: StructureState | None = None,
    ) -> MarketStructure:
        """Run full structure analysis on a candle series."""
        if not candles:
            raise ValueError("Candles required for structure detection")

        sorted_candles = sorted(
            [c for c in candles if c.is_closed],
            key=lambda c: c.open_time_utc,
        )
        if not sorted_candles:
            sorted_candles = sorted(candles, key=lambda c: c.open_time_utc)

        symbol = sorted_candles[0].symbol
        timeframe = sorted_candles[0].timeframe
        analysis_time = sorted_candles[-1].close_time_utc

        internal_highs, internal_lows = self._swing_detector.detect(
            sorted_candles,
            self._config.internal_swing_lookback,
        )
        external_highs, external_lows = self._swing_detector.detect(
            sorted_candles,
            self._config.external_swing_lookback,
        )

        swing_highs, swing_lows = self._swing_detector.detect(
            sorted_candles,
            self._config.swing_lookback,
        )
        swing_highs = self._swing_detector.deduplicate_swings(swing_highs)
        swing_lows = self._swing_detector.deduplicate_swings(swing_lows)

        (
            labeled_highs,
            labeled_lows,
            hh,
            hl,
            lh,
            ll,
        ) = self._swing_detector.label_swings(swing_highs, swing_lows)

        trend, evidence, confidence = self._trend_analyzer.determine_trend(
            labeled_highs,
            labeled_lows,
        )

        if prior_state and prior_state.trend != TrendDirection.UNDETERMINED:
            if trend == TrendDirection.UNDETERMINED:
                trend = prior_state.trend

        bos_events = self._bos_detector.detect(
            sorted_candles,
            labeled_highs,
            labeled_lows,
            trend,
            timeframe,
        )
        choch_events = self._choch_detector.detect(
            sorted_candles,
            labeled_highs,
            labeled_lows,
            trend,
            timeframe,
        )

        internal_labeled = self._swing_detector.label_swings(internal_highs, internal_lows)
        external_labeled = self._swing_detector.label_swings(external_highs, external_lows)
        internal_trend, internal_evidence, _ = self._trend_analyzer.determine_trend(
            internal_labeled[0],
            internal_labeled[1],
        )
        external_trend, external_evidence, _ = self._trend_analyzer.determine_trend(
            external_labeled[0],
            external_labeled[1],
        )

        internal_state = self._trend_analyzer.build_structure_state(
            internal_trend,
            internal_highs,
            internal_lows,
            len(sorted_candles),
        )
        external_state = self._trend_analyzer.build_structure_state(
            external_trend,
            external_highs,
            external_lows,
            len(sorted_candles),
        )
        current_state = self._trend_analyzer.build_structure_state(
            trend,
            labeled_highs,
            labeled_lows,
            len(sorted_candles),
        )
        if bos_events:
            current_state = current_state.model_copy(update={"last_bos": bos_events[-1]})
        if choch_events:
            current_state = current_state.model_copy(update={"last_choch": choch_events[-1]})

        structure_events = self._build_events(
            labeled_highs,
            labeled_lows,
            trend,
            prior_state,
            timeframe,
            bos_events,
            choch_events,
        )

        all_evidence = evidence + internal_evidence + external_evidence
        if bos_events:
            all_evidence.append(f"BOS detected: {bos_events[-1].direction.value}")
        if choch_events:
            all_evidence.append(f"CHoCH detected: {choch_events[-1].direction.value}")

        if confidence < Decimal(str(self._config.min_confidence)):
            if trend != TrendDirection.UNDETERMINED:
                all_evidence.append("Confidence below minimum threshold")

        return MarketStructure(
            symbol=symbol,
            timeframe=timeframe,
            timestamp_utc=analysis_time,
            current_trend=trend,
            swing_highs=labeled_highs,
            swing_lows=labeled_lows,
            higher_highs=hh,
            higher_lows=hl,
            lower_highs=lh,
            lower_lows=ll,
            bos_events=bos_events,
            choch_events=choch_events,
            internal_structure=internal_state,
            external_structure=external_state,
            current_structure_state=current_state,
            structure_events=structure_events,
            evidence=all_evidence,
            confidence=confidence,
        )

    def _build_events(
        self,
        swing_highs: list[SwingPoint],
        swing_lows: list[SwingPoint],
        trend: TrendDirection,
        prior_state: StructureState | None,
        timeframe: str,
        bos_events: list[BOSEvent],
        choch_events: list[CHoCHEvent],
    ) -> list[StructureEvent]:
        events: list[StructureEvent] = []

        for swing in swing_highs + swing_lows:
            events.append(
                StructureEvent(
                    kind=StructureEventKind.SWING_DETECTED,
                    timestamp_utc=swing.timestamp_utc,
                    timeframe=timeframe,
                    description=f"{swing.kind.value} {swing.label.value} at {swing.price}",
                    price=swing.price,
                )
            )

        for bos in bos_events:
            events.append(
                StructureEvent(
                    kind=StructureEventKind.BOS_DETECTED,
                    timestamp_utc=bos.timestamp_utc,
                    timeframe=timeframe,
                    description=f"BOS {bos.direction.value} through {bos.broken_level}",
                    price=bos.break_price,
                )
            )

        for choch in choch_events:
            events.append(
                StructureEvent(
                    kind=StructureEventKind.CHOCH_DETECTED,
                    timestamp_utc=choch.timestamp_utc,
                    timeframe=timeframe,
                    description=f"CHoCH {choch.direction.value} through {choch.broken_level}",
                    price=choch.break_price,
                )
            )

        if prior_state and prior_state.trend != trend:
            events.append(
                StructureEvent(
                    kind=StructureEventKind.TREND_CHANGED,
                    timestamp_utc=datetime.now(tz=UTC),
                    timeframe=timeframe,
                    description=f"Trend changed from {prior_state.trend.value} to {trend.value}",
                    trend=trend,
                )
            )

        events.append(
            StructureEvent(
                kind=StructureEventKind.STRUCTURE_UPDATED,
                timestamp_utc=datetime.now(tz=UTC),
                timeframe=timeframe,
                description=f"Structure updated — trend {trend.value}",
                trend=trend,
            )
        )

        return sorted(events, key=lambda e: e.timestamp_utc)
