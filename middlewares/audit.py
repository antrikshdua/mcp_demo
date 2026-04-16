"""
Custom MCP middleware -- audit logging and request counting.
"""

import time

from fastmcp.server.middleware.middleware import Middleware

from core.lifespan import AppState


class AuditMiddleware(Middleware):
    """
    Logs every MCP request with timestamp, method, and duration.
    In production, ship these logs to your SIEM / audit trail.
    """

    async def on_request(self, context, call_next):
        start = time.perf_counter()
        method = getattr(context.message, "method", "unknown")
        print(f"[audit] >> {method}")
        try:
            result = await call_next(context)
            elapsed_ms = (time.perf_counter() - start) * 1000
            print(f"[audit] << {method} completed in {elapsed_ms:.1f}ms")
            return result
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            print(f"[audit] !! {method} failed in {elapsed_ms:.1f}ms -- {type(exc).__name__}: {exc}")
            raise


class RequestCounterMiddleware(Middleware):
    """Increments the shared request counter in AppState."""

    async def on_request(self, context, call_next):
        lifespan_ctx = getattr(context, "lifespan_context", None)
        if isinstance(lifespan_ctx, AppState):
            lifespan_ctx.request_count += 1
        return await call_next(context)
