"""Shared pytest fixtures for Market Data Engine tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.engines.market_data.config import MarketDataConfig
from backend.engines.market_data.events import EventPublisher
from backend.engines.market_data.schemas import NormalizedCandle
from backend.engines.market_data.timeframes import Timeframe


@dataclass
class MockTerminalInfo:
    name: str = "MetaTrader 5"
    connected: bool = True


@dataclass
class MockAccountInfo:
    login: int = 12345678
    server: str = "XMGlobal-MT5"
    company: str = "XM Global Limited"
    balance: float = 10000.0


@dataclass
class MockSymbolInfo:
    name: str
    description: str = "Gold vs US Dollar"
    digits: int = 2
    point: float = 0.01
    trade_mode: int = 4
    visible: bool = True
    session_deals: int = 0
    session_buy_orders: int = 0
    session_sell_orders: int = 0


@dataclass
class MockTick:
    bid: float
    ask: float
    time: int


@dataclass
class MockRate:
    time: int
    open: float
    high: float
    low: float
    close: float
    tick_volume: int


class MockMT5Client:
    """Configurable mock MT5 client for unit tests."""

    TIMEFRAME_M1 = 1
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_M30 = 30
    TIMEFRAME_H1 = 60
    TIMEFRAME_H4 = 240
    TIMEFRAME_D1 = 1440

    def __init__(self) -> None:
        self.initialize_result = True
        self.terminal_info_obj = MockTerminalInfo()
        self.account_info_obj = MockAccountInfo()
        self.login_result = True
        self.symbols: list[MockSymbolInfo] = [MockSymbolInfo(name="XAUUSD")]
        self.ticks: dict[str, MockTick] = {}
        self.rates: dict[tuple[str, int], list[MockRate]] = {}
        self.last_error_value = (0, "No error")
        self.initialize_calls: list[str] = []
        self.shutdown_called = False
        self.login_calls: list[tuple[int, str, str]] = []

    def initialize(self, path: str = "") -> bool:
        self.initialize_calls.append(path)
        return self.initialize_result

    def shutdown(self) -> None:
        self.shutdown_called = True

    def last_error(self) -> tuple[int, str]:
        return self.last_error_value

    def terminal_info(self) -> MockTerminalInfo | None:
        if not self.initialize_result:
            return None
        return self.terminal_info_obj

    def account_info(self) -> MockAccountInfo | None:
        if not self.initialize_result:
            return None
        return self.account_info_obj

    def login(self, login: int, password: str, server: str) -> bool:
        self.login_calls.append((login, password, server))
        return self.login_result

    def symbols_get(self) -> list[MockSymbolInfo] | None:
        if not self.initialize_result:
            return None
        return self.symbols

    def symbol_info(self, symbol: str) -> MockSymbolInfo | None:
        for item in self.symbols:
            if item.name == symbol:
                return item
        return None

    def symbol_select(self, symbol: str, enable: bool) -> bool:
        return self.symbol_info(symbol) is not None

    def symbol_info_tick(self, symbol: str) -> MockTick | None:
        return self.ticks.get(symbol)

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> list[MockRate] | None:
        key = (symbol, timeframe)
        bars = self.rates.get(key, [])
        if not bars:
            return None
        if start_pos >= len(bars):
            return []
        end = max(len(bars) - start_pos, 0)
        start = max(len(bars) - start_pos - count, 0)
        return bars[start:end]

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime,
        date_to: datetime,
    ) -> list[MockRate] | None:
        key = (symbol, timeframe)
        bars = self.rates.get(key, [])
        if not bars:
            return None
        result = []
        for bar in bars:
            bar_time = datetime.fromtimestamp(bar.time, tz=UTC)
            if date_from <= bar_time <= date_to:
                result.append(bar)
        return result

    def get_timeframe_constants(self) -> dict[str, int]:
        return {
            "TIMEFRAME_M1": self.TIMEFRAME_M1,
            "TIMEFRAME_M5": self.TIMEFRAME_M5,
            "TIMEFRAME_M15": self.TIMEFRAME_M15,
            "TIMEFRAME_M30": self.TIMEFRAME_M30,
            "TIMEFRAME_H1": self.TIMEFRAME_H1,
            "TIMEFRAME_H4": self.TIMEFRAME_H4,
            "TIMEFRAME_D1": self.TIMEFRAME_D1,
        }

    def seed_h1_bars(self, symbol: str, start: datetime, count: int) -> None:
        bars: list[MockRate] = []
        for index in range(count):
            open_time = start + timedelta(hours=index)
            open_price = 2300.0 + index
            bars.append(
                MockRate(
                    time=int(open_time.timestamp()),
                    open=open_price,
                    high=open_price + 2,
                    low=open_price - 1,
                    close=open_price + 1,
                    tick_volume=100 + index,
                )
            )
        self.rates[(symbol, self.TIMEFRAME_H1)] = bars

    def seed_tick(self, symbol: str, *, bid: float = 2350.0, ask: float = 2350.5) -> None:
        self.ticks[symbol] = MockTick(
            bid=bid,
            ask=ask,
            time=int(datetime.now(tz=UTC).timestamp()),
        )


@pytest.fixture
def sample_symbol() -> str:
    return "XAUUSD"


@pytest.fixture
def market_data_config() -> MarketDataConfig:
    return MarketDataConfig(
        symbol="XAUUSD",
        broker="XMGlobal",
        timeframes=["M1", "H1"],
        tick_enabled=True,
        history_bars=100,
        stale_threshold_sec=30,
        mt5_login="12345678",
        mt5_password="secret",
        mt5_server="XMGlobal-MT5",
    )


@pytest.fixture
def mock_mt5_client() -> MockMT5Client:
    client = MockMT5Client()
    client.seed_tick("XAUUSD")
    client.seed_h1_bars("XAUUSD", datetime(2026, 1, 1, tzinfo=UTC), 10)
    return client


@pytest.fixture
def event_publisher() -> EventPublisher:
    return EventPublisher()


@pytest.fixture
def sample_candles(sample_symbol: str) -> list[NormalizedCandle]:
    start = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    candles: list[NormalizedCandle] = []
    for index in range(5):
        open_time = start + timedelta(hours=index)
        open_price = Decimal("2300") + Decimal(index)
        candles.append(
            NormalizedCandle(
                symbol=sample_symbol,
                timeframe=Timeframe.H1.value,
                open=open_price,
                high=open_price + Decimal("2"),
                low=open_price - Decimal("1"),
                close=open_price + Decimal("1"),
                volume=100,
                open_time_utc=open_time,
                close_time_utc=open_time + timedelta(hours=1),
                is_closed=True,
            )
        )
    return candles
