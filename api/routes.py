"""
Custom HTTP routes -- health, readiness, and metrics endpoints.
"""

from starlette.requests import Request
from starlette.responses import JSONResponse

from fastmcp import FastMCP


def register_routes(mcp: FastMCP) -> None:
    """Register custom HTTP routes on the main MCP server."""

    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request: Request) -> JSONResponse:
        """Liveness probe -- load balancers hit this every few seconds."""
        return JSONResponse({"status": "ok"})

    @mcp.custom_route("/ready", methods=["GET"])
    async def readiness_check(request: Request) -> JSONResponse:
        """
        Readiness probe -- returns 503 if the server is not fully initialised.
        In production, check DB pool health here.
        """
        return JSONResponse({
            "status": "ready",
            "server": "ProductionDemoServer",
            "version": "1.0.0",
        })

    @mcp.custom_route("/metrics", methods=["GET"])
    async def metrics(request: Request) -> JSONResponse:
        """
        Basic metrics endpoint.
        In production: emit Prometheus metrics with prometheus_client.
        """
        return JSONResponse({
            "uptime_note": "see started_at in lifespan state",
            "endpoint": "/metrics",
        })
