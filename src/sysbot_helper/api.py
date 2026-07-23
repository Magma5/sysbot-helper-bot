import asyncio
import traceback
from typing import Any, Callable

from aiohttp import web
from pydantic import BaseModel


@web.middleware
async def error_middleware(request: web.Request, handler: Callable) -> web.Response:
    """
    Global middleware to catch unhandled exceptions and serialize them into standard JSON error objects.
    This prevents raw HTML 500 pages from being sent to API clients.
    """
    try:
        response = await handler(request)
        return response
    except web.HTTPException as e:
        return web.json_response({"error": e.reason}, status=e.status)
    except Exception as e:
        traceback.print_exc()
        return web.json_response({"error": str(e)}, status=500)


def json_response(data: Any, **kwargs) -> web.Response:
    """
    Explicitly serialize a dict or Pydantic BaseModel into a web.Response.
    Named identically to aiohttp.web.json_response for intuition, but enhanced to support Pydantic.
    """
    if isinstance(data, BaseModel):
        data = data.model_dump()
    return web.json_response(data, **kwargs)


class APIRouter:
    """
    Modular router for API endpoints. Provides explicit method binding similar to
    aiohttp.web.UrlDispatcher, but allows defining a prefix for a group of endpoints.
    """
    def __init__(self, prefix: str = ""):
        self.prefix = prefix
        self.routes = web.RouteTableDef()

    def add_get(self, path: str, handler: Callable) -> None:
        self.routes.get(self.prefix + path)(handler)

    def add_post(self, path: str, handler: Callable) -> None:
        self.routes.post(self.prefix + path)(handler)

    def add_head(self, path: str, handler: Callable) -> None:
        self.routes.head(self.prefix + path)(handler)

    def add_put(self, path: str, handler: Callable) -> None:
        self.routes.put(self.prefix + path)(handler)


class APIServer:
    """
    First-class API framework manager that hooks into the core Bot lifecycle.
    """
    def __init__(self, bot, listen: str = "localhost", port: int = 8080):
        self.bot = bot
        self.listen = listen
        self.port = port
        self.app = web.Application(
            client_max_size=500 * 1024 * 1024,
            middlewares=[error_middleware]
        )
        self.app["bot"] = bot
        self.site_task: asyncio.Task | None = None
        self.runner: web.AppRunner | None = None

    def add_router(self, router: APIRouter) -> None:
        """Mount a modular APIRouter onto the application."""
        self.app.add_routes(router.routes)

    async def start(self) -> None:
        """Start the aiohttp server in the background."""
        if self.site_task is not None:
            return

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        site = web.TCPSite(self.runner, self.listen, self.port)
        self.site_task = asyncio.create_task(site.start())

    async def stop(self) -> None:
        """Gracefully stop the aiohttp server."""
        if self.site_task:
            self.site_task.cancel()
        if self.runner:
            await self.runner.cleanup()
