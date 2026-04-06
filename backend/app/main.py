from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, install_request_logging
from app.db.session import ensure_database

configure_logging()
settings = get_settings()

PRIVATE_NETWORK_ORIGIN_REGEX = (
    r"^https?://("
    r"localhost|127\.0\.0\.1|"
    r"10(?:\.\d{1,3}){3}|"
    r"192\.168(?:\.\d{1,3}){2}|"
    r"172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2}"
    r")(?::\d+)?$"
)


def build_cors_options() -> tuple[list[str], str | None]:
    allow_origins = [settings.frontend_url, "http://localhost:5173"]
    allow_origin_regex = PRIVATE_NETWORK_ORIGIN_REGEX if settings.app_env == "development" else None
    return allow_origins, allow_origin_regex


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    ensure_database()
    yield


app = FastAPI(title="EVE Station Trader API", version="0.1.0", lifespan=lifespan)
install_request_logging(app)

allow_origins, allow_origin_regex = build_cors_options()

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router, prefix="/api")
