import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.chat import router as chat_router
from app.api.routes.events import router as events_router
from app.api.routes.filesystem import router as filesystem_router
from app.api.routes.mcp import router as mcp_router
from app.api.routes.observations import router as observations_router
from app.api.routes.projects import router as projects_router
from app.api.routes.settings import router as settings_router
from app.api.routes.tools import router as tools_router
from app.config.settings import get_settings
from app.core.container import AppContainer, set_container
from app.db.seed import seed_app_data
from app.db.session import get_sessionmaker
from app.mcp.client_manager import MCPClientManager, get_mcp_client_manager
from app.mcp.transports import *  # noqa: F401, F403 - registers stdio transport
from app.middleware.error_handler import (
    ServiceError,
    catch_all_handler,
    service_error_handler,
    validation_error_handler,
)
from app.providers.openrouter.model_catalog import OpenRouterModelCatalogService
from app.services.agent_task_manager import AgentTaskManager
from app.services.approval_waiter import ApprovalWaiter
from app.services.event_bus import EventBus
from app.services.memory.observational.background import OMBackgroundRunner
from app.tools.registry import ToolRegistry
from app.tools.registry import get_tool_registry

logger = logging.getLogger(__name__)


def _configure_app_logging() -> None:
    """Ensure app.* logs are visible under the same sink as uvicorn error logs."""
    app_logger = logging.getLogger("app")
    uvicorn_error_logger = logging.getLogger("uvicorn.error")

    if uvicorn_error_logger.handlers:
        app_logger.handlers = list(uvicorn_error_logger.handlers)
        app_logger.setLevel(uvicorn_error_logger.level or logging.INFO)
        app_logger.propagate = False
        return

    if not app_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(levelname)s:     %(name)s - %(message)s")
        )
        app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_app_logging()

    # Build app-scoped container and set adapter hooks.
    container = AppContainer(
        event_bus=EventBus(),
        tool_registry=ToolRegistry(),
        om_runner=OMBackgroundRunner(),
        approval_waiter=ApprovalWaiter(),
        agent_task_manager=AgentTaskManager(),
        mcp_client_manager=MCPClientManager(),
    )
    container.tool_registry.register_builtin_plugins()
    app.state.container = container
    set_container(container)

    # Schema managed by Alembic; sync DB work in its own session block
    session_factory = get_sessionmaker()
    with session_factory() as session:
        seed_app_data(session)
        session.commit()

    # Async operations each get their own session
    # Sync provider models using DB-stored API keys
    with session_factory() as session:
        from app.db.repositories.settings_repo import SettingsRepository
        from app.providers.groq.model_catalog import GroqModelCatalogService
        from app.services.api_key_resolver import APIKeyResolver

        repo = SettingsRepository(session)
        resolver = APIKeyResolver(repo)

        or_client = resolver.create_client("openrouter")
        if or_client:
            await OpenRouterModelCatalogService(session, client=or_client).sync_models_on_startup()
        else:
            logger.info("No OpenRouter API key configured - skipping model sync")

        groq_client = resolver.create_client("groq")
        if groq_client:
            await GroqModelCatalogService(session, client=groq_client).sync_models_on_startup()
        else:
            logger.info("No Groq API key configured - skipping model sync")

        from app.providers.openai_sub.model_catalog import OpenAISubModelCatalogService

        openai_sub_client = resolver.create_client("openai-sub")
        if openai_sub_client:
            catalog = OpenAISubModelCatalogService(session, client=openai_sub_client)
            await catalog.sync_models_on_startup()
        else:
            logger.info("No OpenAI Subscription configured - skipping model sync")

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

    settings = get_settings()
    if settings.oauth_redirect_uri:
        from app.providers.openai_sub.callback_proxy import start_callback_proxy

        start_callback_proxy(settings.oauth_redirect_uri, settings.oauth_redirect_base)

    yield

    if settings.oauth_redirect_uri:
        from app.providers.openai_sub.callback_proxy import stop_callback_proxy

        stop_callback_proxy()
    set_container(None)


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
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(ServiceError, service_error_handler)
    app.add_exception_handler(Exception, catch_all_handler)

    app.include_router(projects_router)
    app.include_router(filesystem_router)
    app.include_router(settings_router)
    app.include_router(mcp_router)
    app.include_router(chat_router)
    app.include_router(observations_router)
    app.include_router(events_router)
    app.include_router(tools_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
