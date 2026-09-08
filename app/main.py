import os

from chainlit.utils import mount_chainlit
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from app.ai.router import router as ai_router
from app.base.interface import RootResponse
from app.config import Settings, get_settings
from app.health import router as health_router
from app.news.router import router as news_router
from app.notification.router import router as notification_router
from app.signals.router import router as signals_router
from app.ticker.router import router as ticker_router

CHAINLIT_AUTH_SECRET_ENV = "CHAINLIT_AUTH_SECRET"


async def _chainlit_unavailable(scope: Scope, receive: Receive, send: Send) -> None:
    response = JSONResponse(
        status_code=503,
        content={"detail": "Chainlit is not configured"},
    )
    await response(scope, receive, send)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the ASGI application without connecting to external services."""
    resolved_settings = settings or get_settings()
    application = FastAPI()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_origins),
        allow_origin_regex=resolved_settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(news_router)
    application.include_router(ticker_router)
    application.include_router(signals_router)
    application.include_router(ai_router)
    application.include_router(notification_router)
    application.include_router(health_router)
    application.mount("/public", StaticFiles(directory="public"), name="public")
    application.mount("/logo", StaticFiles(directory="public"), name="public")

    @application.get("/", response_model=RootResponse)
    def read_root() -> RootResponse:
        return RootResponse(status=200, message="Monii 0.1.0")

    if os.environ.get(CHAINLIT_AUTH_SECRET_ENV):
        mount_chainlit(app=application, target="app/chainlit/chainlit.py", path="/chat")
    else:
        application.mount("/chat", _chainlit_unavailable, name="chat")
    return application


app = create_app()
