"""
main.py -- Entry point for the modular FastMCP server.

HOW TO RUN
----------
# Run as STDIO server (for Claude Desktop / Cursor)
python main.py

# Run as HTTP server on port 8000
python main.py --http

# Run the built-in smoke-test demo (no pytest needed)
python main.py --demo

# Run with a specific port
python main.py --http --port 9000
"""

from __future__ import annotations

import asyncio
import argparse
import os
import sys

from core.server import create_server
from demo import run_demo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="FastMCP Production Demo Server (Modular)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--http", action="store_true",
        help="Run as HTTP server (default: STDIO for local MCP clients)",
    )
    parser.add_argument(
        "--host", default=os.getenv("FASTMCP_HOST", "127.0.0.1"),
        help="Bind host for HTTP transport (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port", type=int, default=int(os.getenv("FASTMCP_PORT", "8000")),
        help="Bind port for HTTP transport (default: 8000)",
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="Run in-process demo and exit (no server, no network)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    mcp = create_server()

    if args.demo:
        asyncio.run(run_demo(mcp))
        sys.exit(0)

    if args.http:
        print(f"[server] Starting HTTP transport on {args.host}:{args.port}")
        print(f"[server] MCP endpoint : http://{args.host}:{args.port}/mcp")
        print(f"[server] Health check  : http://{args.host}:{args.port}/health")
        print(f"[server] Readiness     : http://{args.host}:{args.port}/ready")
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        print("[server] Starting STDIO transport (for local MCP clients)", file=sys.stderr)
        mcp.run(transport="stdio")
