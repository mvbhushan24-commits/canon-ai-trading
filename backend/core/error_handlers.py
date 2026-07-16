"""FastAPI exception handler registration (foundation only)."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.core.exceptions import CanonTradingError, ConfigurationError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers. No business logic."""

    @app.exception_handler(CanonTradingError)
    async def handle_canon_error(_request: Request, exc: CanonTradingError) -> JSONResponse:
        logger.error(
            "Application error: %s", exc.message, extra={"code": exc.code, "details": exc.details}
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(ConfigurationError)
    async def handle_configuration_error(
        _request: Request, exc: ConfigurationError
    ) -> JSONResponse:
        logger.error("Configuration error: %s", exc.message, extra={"details": exc.details})
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )
