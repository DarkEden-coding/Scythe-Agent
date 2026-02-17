import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.chat import router as chat_router
from app.api.routes.events import router as events_router
from app.api.routes.filesystem import router as filesystem_router
from app.api.routes.projects import router as projects_router
from app.api.routes.settings import router as settings_router
from app.config.settings import get_settings
from app.db.seed import seed_demo_data
from app.db.session import get_engine, get_sessionmaker
from app.mcp.client_manager import get_mcp_client_manager
from app.middleware.error_handler import ServiceError, catch_all_handler, service_error_handler
from app.providers.openrouter.model_catalog import OpenRouterModelCatalogService
from app.tools.registry import get_tool_registry

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Schema managed by Alembic; sync DB work in its own session block
    session_factory = get_sessionmaker()
    with session_factory() as session:
        seed_demo_data(session)
        session.commit()

    # Async operations each get their own session
    # Sync OpenRouter models using DB-stored API key
    with session_factory() as session:
        from app.db.repositories.settings_repo import SettingsRepository
        from app.services.api_key_resolver import APIKeyResolver

        repo = SettingsRepository(session)
        resolver = APIKeyResolver(repo)
        client = resolver.create_client()
        if client:
            await OpenRouterModelCatalogService(session, client=client).sync_models_on_startup()
        else:
            logger.info("No OpenRouter API key configured - skipping model sync")

    with session_factory() as session:
        try:
            manager = get_mcp_client_manager()
            discovered, _errors = await manager.discover_and_cache_tools(session)
            get_tool_registry().register_mcp_tools(
                [
                    {
                        "server_id": tool.server_id,
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.input_schema,
                    }
                    for tool in discovered
                ]
            )
        except Exception:
            logger.warning("MCP tool discovery failed during startup", exc_info=True)

    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register error handlers
    app.add_exception_handler(ServiceError, service_error_handler)
    app.add_exception_handler(Exception, catch_all_handler)

    app.include_router(projects_router)
    app.include_router(filesystem_router)
    app.include_router(settings_router)
    app.include_router(chat_router)
    app.include_router(events_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
