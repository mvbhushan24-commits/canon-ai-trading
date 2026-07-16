"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.core.config import get_settings
from backend.core.error_handlers import register_exception_handlers
from backend.core.logging import configure_logging
from backend.engines.market_data import MarketDataEngine, load_market_data_config

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)

    market_data_config = load_market_data_config(settings)
    logger.info(
        "Market Data configuration loaded",
        extra={
            "symbol": market_data_config.symbol,
            "broker": market_data_config.broker,
            "timeframes": market_data_config.timeframes,
        },
    )

    market_data_engine = MarketDataEngine(config=market_data_config)
    app.state.market_data_engine = market_data_engine
    logger.info("Market Data Engine components initialized")

    market_data_engine.start()
    logger.info(
        "Market Data Engine started",
        extra={"status": market_data_engine.get_status().model_dump(mode="json")},
    )

    yield

    market_data_engine.stop()


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Canon AI Trading — Gold (XAUUSD) Trading Intelligence Platform",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

register_exception_handlers(app)
