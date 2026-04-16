"""
Agent CLI entry point.

Usage:
    python -m agent.cli
    python -m agent.cli --query "What is 12 factorial?"
    python -m agent.cli --model "lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF"
    python -m agent.cli --base-url http://localhost:1234/v1
    python -m agent.cli --max-iterations 5
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from .config import DEFAULT_BASE_URL, DEFAULT_API_KEY, DEFAULT_MODEL, DEFAULT_MAX_ITERATIONS
from .chat_session import chat_session

# Import the server factory -- lazy to avoid circular imports
from core.server import create_server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Chat with a local LM Studio model that can use your FastMCP tools.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--base-url", default=DEFAULT_BASE_URL,
        help=f"LM Studio server URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--api-key", default=DEFAULT_API_KEY,
        help="API key placeholder (LM Studio does not enforce one)",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=(
            "Model identifier shown in LM Studio (default: 'local-model'). "
            "Copy the exact string from the LM Studio UI."
        ),
    )
    parser.add_argument(
        "--query", default=None,
        help="Run a single query and exit instead of starting the interactive REPL.",
    )
    parser.add_argument(
        "--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS,
        help=f"Maximum tool-call iterations per turn (default: {DEFAULT_MAX_ITERATIONS})",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print each tool call and its raw result while running.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    mcp = create_server()
    asyncio.run(chat_session(args, mcp))
