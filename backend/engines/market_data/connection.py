"""MT5 connection manager."""

import logging
from datetime import UTC, datetime

from backend.engines.market_data.config import MarketDataConfig
from backend.engines.market_data.events import EventPublisher
from backend.engines.market_data.exceptions import MT5AuthenticationError, MT5ConnectionError
from backend.engines.market_data.mt5_protocol import MT5ClientProtocol
from backend.engines.market_data.schemas import EngineConnectionStatus

logger = logging.getLogger(__name__)


class MT5ConnectionManager:
    """Initialize, verify, and shutdown the MT5 terminal connection."""

    def __init__(
        self,
        config: MarketDataConfig,
        client: MT5ClientProtocol,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._event_publisher = event_publisher
        self._connected = False
        self._last_error: str | None = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def connect(self) -> None:
        """Initialize MT5, verify terminal availability, and verify login session."""
        logger.info(
            "Initializing MT5 connection",
            extra={"broker": self._config.broker, "terminal_path": self._config.mt5_terminal_path},
        )

        initialized = self._client.initialize(self._config.mt5_terminal_path)
        if not initialized:
            code, message = self._client.last_error()
            self._last_error = message
            logger.error(
                "MT5 initialization failed",
                extra={"code": "MDE_CONN_FAILED", "mt5_code": code, "details": message},
            )
            self._emit_connection_lost(message)
            raise MT5ConnectionError(
                f"MT5 initialization failed: {message}",
                details={"mt5_code": code},
            )

        terminal_info = self._client.terminal_info()
        if terminal_info is None:
            code, message = self._client.last_error()
            self._last_error = message
            logger.error(
                "MT5 terminal unavailable",
                extra={"code": "MDE_CONN_FAILED", "mt5_code": code},
            )
            self._emit_connection_lost(message)
            raise MT5ConnectionError(
                f"MT5 terminal unavailable: {message}",
                details={"mt5_code": code},
            )

        logger.info(
            "MT5 terminal available",
            extra={
                "terminal_name": getattr(terminal_info, "name", "unknown"),
                "connected": getattr(terminal_info, "connected", False),
            },
        )

        self._verify_login_session()
        self._connected = True
        self._last_error = None
        logger.info("MT5 connection established")
        if self._event_publisher is not None:
            self._event_publisher.publish_connection_established(
                broker=self._config.broker,
                terminal_name=getattr(terminal_info, "name", "unknown"),
            )

    def _verify_login_session(self) -> None:
        account_info = self._client.account_info()
        if account_info is not None:
            logger.info(
                "MT5 login session verified",
                extra={
                    "login": getattr(account_info, "login", None),
                    "server": getattr(account_info, "server", None),
                },
            )
            return

        has_credentials = (
            self._config.mt5_login
            and self._config.mt5_password
            and self._config.mt5_server
        )
        if not has_credentials:
            code, message = self._client.last_error()
            self._last_error = message
            logger.error(
                "MT5 login session missing and credentials not configured",
                extra={"code": "MDE_AUTH_FAILED"},
            )
            raise MT5AuthenticationError(
                "MT5 login session not active and credentials are not configured",
                details={"mt5_code": code},
            )

        try:
            login_id = int(self._config.mt5_login)
        except ValueError as exc:
            raise MT5AuthenticationError(
                "MT5 login must be numeric",
                details={"login": self._config.mt5_login},
            ) from exc

        logged_in = self._client.login(
            login_id,
            self._config.mt5_password,
            self._config.mt5_server,
        )
        if not logged_in:
            code, message = self._client.last_error()
            self._last_error = message
            logger.error(
                "MT5 authentication failed",
                extra={"code": "MDE_AUTH_FAILED", "mt5_code": code},
            )
            raise MT5AuthenticationError(
                f"MT5 authentication failed: {message}",
                details={"mt5_code": code},
            )

        account_info = self._client.account_info()
        if account_info is None:
            code, message = self._client.last_error()
            self._last_error = message
            raise MT5AuthenticationError(
                f"MT5 account info unavailable after login: {message}",
                details={"mt5_code": code},
            )

        logger.info(
            "MT5 login successful",
            extra={
                "login": getattr(account_info, "login", None),
                "server": getattr(account_info, "server", None),
            },
        )

    def disconnect(self) -> None:
        """Gracefully shutdown the MT5 connection."""
        if not self._connected:
            logger.info("MT5 disconnect skipped — not connected")
            return

        logger.info("Shutting down MT5 connection")
        self._client.shutdown()
        self._connected = False
        logger.info("MT5 connection closed")

    def get_connection_status(self) -> EngineConnectionStatus:
        if not self._connected:
            return EngineConnectionStatus.DISCONNECTED
        if self._last_error:
            return EngineConnectionStatus.ERROR
        terminal_info = self._client.terminal_info()
        if terminal_info is None or not getattr(terminal_info, "connected", False):
            return EngineConnectionStatus.DEGRADED
        return EngineConnectionStatus.CONNECTED

    def _emit_connection_lost(self, message: str) -> None:
        if self._event_publisher is not None:
            self._event_publisher.publish_connection_lost(
                error=message,
                timestamp_utc=datetime.now(tz=UTC),
            )
