import logging
import sys
from time import perf_counter

from fastapi import FastAPI, Request

request_logger = logging.getLogger("app.requests")
_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=_LOG_FORMAT,
        force=True,
    )
    _configure_app_logger("app.requests", logging.INFO)
    _configure_app_logger("app.db.queries", logging.INFO)
    _configure_app_logger("app.imports", logging.INFO)
    _configure_app_logger("uvicorn.access", logging.INFO)
    _configure_app_logger("uvicorn.error", logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)


def _configure_app_logger(name: str, level: int) -> None:
    logger = logging.getLogger(name)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False


def install_request_logging(app: FastAPI) -> None:
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = perf_counter()
        response = await call_next(request)
        duration_ms = (perf_counter() - start) * 1000
        request_logger.info(
            '%s %s -> %s (%.2f ms)',
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
