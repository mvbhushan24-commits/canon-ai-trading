"""Unit tests for decision event publisher."""

from datetime import UTC, datetime

from backend.engines.market_decision.publisher import DecisionEventPublisher
from backend.engines.market_decision.schemas import DecisionMetadata, DecisionState, TradeDecision, TradeDirection


def _sample_decision(*, state: DecisionState = DecisionState.BUY) -> TradeDecision:
    return TradeDecision(
        decision_id="dec-1",
        symbol="XAUUSD",
        timestamp_utc=datetime(2026, 1, 14, 8, 30, tzinfo=UTC),
        state=state,
        direction=TradeDirection.BUY if state is DecisionState.BUY else TradeDirection.NONE,
        confidence=72,
        quality_score=80,
        metadata=DecisionMetadata(engines_available=8, engines_stale=0),
        blocking_reasons=["blocked"] if state is DecisionState.NO_TRADE else [],
        error_codes=["LOW_CONFIDENCE"] if state is DecisionState.NO_TRADE else [],
    )


def test_publish_decision_created_dual_events() -> None:
    publisher = DecisionEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    publisher.publish_decision_created(_sample_decision())

    assert "DecisionCreated" in received
    assert "decision.completed" in received


def test_publish_decision_published_for_signals() -> None:
    publisher = DecisionEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    publisher.publish_decision_published(_sample_decision())

    assert "DecisionPublished" in received
    assert "decision.signal.published" in received


def test_publish_decision_rejected_no_trade() -> None:
    publisher = DecisionEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    publisher.publish_decision_rejected(_sample_decision(state=DecisionState.NO_TRADE))

    assert "DecisionRejected" in received
    assert "decision.no_trade.published" in received


def test_publish_decision_rejected_invalid() -> None:
    publisher = DecisionEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    publisher.publish_decision_rejected(_sample_decision(state=DecisionState.INVALID))

    assert "decision.error" in received


def test_publish_decision_updated() -> None:
    publisher = DecisionEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))
    prior = _sample_decision()
    current = _sample_decision()
    current = current.model_copy(update={"confidence": 80})

    publisher.publish_decision_updated(prior, current, "confidence increased")

    assert "DecisionUpdated" in received
    assert "decision.updated" in received


def test_publish_decision_expired() -> None:
    publisher = DecisionEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    decision = _sample_decision().model_copy(
        update={"valid_until_utc": datetime(2026, 1, 14, 9, 30, tzinfo=UTC)},
    )
    publisher.publish_decision_expired(decision)

    assert "DecisionExpired" in received
    assert "decision.expired" in received


def test_wildcard_handler_receives_all_events() -> None:
    publisher = DecisionEventPublisher()
    count = 0

    def handler(_event) -> None:
        nonlocal count
        count += 1

    publisher.subscribe("*", handler)
    publisher.publish_decision_created(_sample_decision())
    publisher.publish_decision_published(_sample_decision())

    assert count == 4
