"""
Server composition -- assembles the main FastMCP server from sub-servers,
middleware, auth, and custom routes.
"""

from __future__ import annotations

import os

from fastmcp import FastMCP

from core.lifespan import app_lifespan
from middlewares import AuditMiddleware, RequestCounterMiddleware

# Import sub-servers (tools are registered at import time)
from api.v1 import math_mcp, notes_mcp, utils_mcp

# Import resources and prompts so their decorators register on sub-servers
import resources.resources  # noqa: F401
import prompts.prompts      # noqa: F401

from api.routes import register_routes


def create_server() -> FastMCP:
    """Build and return the fully-configured FastMCP server."""

    # Auth setup (swap InMemoryTokenVerifier for JWTVerifier in production)
    try:
        from fastmcp.server.auth.providers.in_memory import InMemoryTokenVerifier
        _auth = InMemoryTokenVerifier(tokens={
            "dev-token-admin":  {"sub": "user-admin",  "role": "admin",  "scopes": ["read", "write", "admin"]},
            "dev-token-reader": {"sub": "user-reader",  "role": "reader", "scopes": ["read"]},
        })
        _auth_available = True
    except ImportError:
        _auth = None
        _auth_available = False

    mcp = FastMCP(
        name="ProductionDemoServer",
        instructions=(
            "A production-grade FastMCP demo server. "
            "Provides note management (create/search/delete), math utilities, "
            "and general-purpose tools. "
            "Start by listing available tools with tools/list."
        ),
        version="1.0.0",
        lifespan=app_lifespan,
        middleware=[
            AuditMiddleware(),
            RequestCounterMiddleware(),
        ],
        # auth=_auth if _auth_available else None,  # Uncomment to require Bearer tokens
        mask_error_details=os.getenv("FASTMCP_MASK_ERROR_DETAILS", "false").lower() == "true",
    )

    # Mount sub-servers with namespaces
    mcp.mount(math_mcp,  namespace="math")
    mcp.mount(notes_mcp, namespace="notes")
    mcp.mount(utils_mcp, namespace="utils")

    # Register custom HTTP routes
    register_routes(mcp)

    return mcp
