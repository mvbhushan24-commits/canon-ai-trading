"""Trend classification from swing structure."""

from decimal import Decimal

from backend.engines.market_structure.schemas import (
    StructureState,
    SwingLabel,
    SwingPoint,
    TrendDirection,
)


class TrendAnalyzer:
    """Determine trend from classified swing points."""

    def determine_trend(
        self,
        swing_highs: list[SwingPoint],
        swing_lows: list[SwingPoint],
    ) -> tuple[TrendDirection, list[str], Decimal]:
        """Return trend direction, evidence, and confidence."""
        evidence: list[str] = []

        recent_highs = [s for s in swing_highs if s.label in {SwingLabel.HH, SwingLabel.LH}]
        recent_lows = [s for s in swing_lows if s.label in {SwingLabel.HL, SwingLabel.LL}]

        if len(recent_highs) < 1 or len(recent_lows) < 1:
            return TrendDirection.UNDETERMINED, ["Insufficient classified swings"], Decimal("0")

        last_high = recent_highs[-1]
        last_low = recent_lows[-1]

        hh_count = sum(1 for s in swing_highs if s.label == SwingLabel.HH)
        hl_count = sum(1 for s in swing_lows if s.label == SwingLabel.HL)
        lh_count = sum(1 for s in swing_highs if s.label == SwingLabel.LH)
        ll_count = sum(1 for s in swing_lows if s.label == SwingLabel.LL)

        bullish_score = hh_count + hl_count
        bearish_score = lh_count + ll_count
        total = bullish_score + bearish_score

        if total == 0:
            return TrendDirection.RANGE, ["No comparable swing progression"], Decimal("0.3")

        if last_high.label == SwingLabel.HH and last_low.label == SwingLabel.HL:
            evidence.append(f"Higher high at {last_high.price} and higher low at {last_low.price}")
            confidence = Decimal(str(min(1.0, bullish_score / total)))
            return TrendDirection.BULLISH, evidence, confidence

        if last_high.label == SwingLabel.LH and last_low.label == SwingLabel.LL:
            evidence.append(f"Lower high at {last_high.price} and lower low at {last_low.price}")
            confidence = Decimal(str(min(1.0, bearish_score / total)))
            return TrendDirection.BEARISH, evidence, confidence

        if bullish_score > bearish_score:
            evidence.append("Mixed structure leaning bullish")
            return TrendDirection.BULLISH, evidence, Decimal(str(bullish_score / total))

        if bearish_score > bullish_score:
            evidence.append("Mixed structure leaning bearish")
            return TrendDirection.BEARISH, evidence, Decimal(str(bearish_score / total))

        evidence.append("Equal bullish and bearish swing signals")
        return TrendDirection.RANGE, evidence, Decimal("0.5")

    def build_structure_state(
        self,
        trend: TrendDirection,
        swing_highs: list[SwingPoint],
        swing_lows: list[SwingPoint],
        bar_count: int,
    ) -> StructureState:
        """Build a structure state snapshot."""
        return StructureState(
            trend=trend,
            last_swing_high=swing_highs[-1] if swing_highs else None,
            last_swing_low=swing_lows[-1] if swing_lows else None,
            bar_count=bar_count,
        )
