import asyncio
import inspect
import logging
import traceback
from collections.abc import Callable
from typing import Any

from aiohttp import web
from pydantic import BaseModel

log = logging.getLogger(__name__)


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
    Modular router for API endpoints using decorator-based route registration
    (@router.get, @router.post, etc.) and metadata tagging.

    Inspired by FastAPI, Flask, and aiohttp RouteTableDef, tailored specifically for Python class-based
    components like discord.py Cogs.
    """

    def __init__(self, prefix: str = ""):
        self.prefix = prefix

    def _normalize_path(self, path: str) -> str:
        """Join prefix and path cleanly, ensuring exactly one leading slash."""
        p1 = self.prefix.strip("/")
        p2 = path.strip("/")
        if p1 and p2:
            return f"/{p1}/{p2}"
        elif p1:
            return f"/{p1}"
        elif p2:
            return f"/{p2}"
        return "/"

    def route(self, method: str, path: str, **kwargs) -> Callable:
        """Generic route decorator (e.g., @router.route("GET", "/path"))."""

        def decorator(handler: Callable) -> Callable:
            if not hasattr(handler, "__route_specs__"):
                handler.__route_specs__ = []
            handler.__route_specs__.append({"method": method.upper(), "path": path, "kwargs": kwargs})
            return handler

        return decorator

    def get(self, path: str, **kwargs) -> Callable:
        """Decorator for GET routes (e.g., @router.get("/hello"))."""
        return self.route("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> Callable:
        """Decorator for POST routes."""
        return self.route("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> Callable:
        """Decorator for PUT routes."""
        return self.route("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs) -> Callable:
        """Decorator for DELETE routes."""
        return self.route("DELETE", path, **kwargs)

    def patch(self, path: str, **kwargs) -> Callable:
        """Decorator for PATCH routes."""
        return self.route("PATCH", path, **kwargs)

    def head(self, path: str, **kwargs) -> Callable:
        """Decorator for HEAD routes."""
        return self.route("HEAD", path, **kwargs)

    def get_routes(self, instance: Any) -> web.RouteTableDef:
        """
        Build an aiohttp.web.RouteTableDef for mounting on an aiohttp web.Application.
        Inspects the bound methods of the instance for route metadata injected by decorators.
        """
        routes = web.RouteTableDef()

        for _, bound_method in inspect.getmembers(instance, predicate=inspect.ismethod):
            underlying_func = getattr(bound_method, "__func__", bound_method)
            specs = getattr(underlying_func, "__route_specs__", None)

            if not specs:
                continue

            for spec in specs:
                full_path = self._normalize_path(spec["path"])
                method_name = spec["method"]
                kwargs = spec["kwargs"]

                route_decorator = getattr(routes, method_name.lower(), None)
                if route_decorator:
                    route_decorator(full_path, **kwargs)(bound_method)
                else:
                    routes.route(method_name, full_path, **kwargs)(bound_method)

        return routes


class APIServer:
    """
    First-class API framework manager that hooks into the core Bot lifecycle.
    """

    def __init__(self, bot, enabled: bool = True, listen: str = "localhost", port: int = 8080):
        self.bot = bot
        self.enabled = enabled
        self.listen = listen
        self.port = port

        if self.enabled:
            self.app = web.Application(client_max_size=500 * 1024 * 1024, middlewares=[error_middleware])
            self.app["bot"] = bot
        else:
            self.app = None

        self.site_task: asyncio.Task | None = None
        self.runner: web.AppRunner | None = None

    def add_router(self, router: APIRouter, instance: Any = None) -> None:
        """Mount a modular APIRouter onto the application."""
        owner = instance.__class__.__name__ if instance else "standalone"
        if not self.enabled:
            log.info(
                "API server disabled; skipped registering routes for %s (prefix: '%s')", owner, router.prefix or "/"
            )
            return

        routes = router.get_routes(instance=instance)
        self.app.add_routes(routes)
        log.info("Registered %d API route(s) for %s (prefix: '%s')", len(routes), owner, router.prefix or "/")

    async def start(self) -> None:
        """Start the aiohttp server in the background."""
        if not self.enabled or self.site_task is not None:
            return

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        site = web.TCPSite(self.runner, self.listen, self.port)
        self.site_task = asyncio.create_task(site.start())

    async def stop(self) -> None:
        """Gracefully stop the aiohttp server."""
        if not self.enabled:
            return

        if self.site_task:
            self.site_task.cancel()
        if self.runner:
            await self.runner.cleanup()
