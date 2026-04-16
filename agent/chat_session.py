"""
Chat session -- interactive REPL and one-shot mode.
"""

from __future__ import annotations

import argparse

from openai import AsyncOpenAI
from fastmcp import Client

from .tool_converter import mcp_tool_to_openai
from .agent_loop import run_agent


async def chat_session(args: argparse.Namespace, mcp_server) -> None:
    """
    Opens an in-process MCP client, discovers tools, then runs an interactive
    REPL that feeds each user message through the agent loop.

    Args:
        args: Parsed CLI arguments.
        mcp_server: The FastMCP server instance to connect to in-process.
    """
    openai_client = AsyncOpenAI(
        base_url=args.base_url,
        api_key=args.api_key,
    )

    print("\nConnecting to MCP server (in-process)...")
    async with Client(mcp_server) as mcp_client:
        # Discover tools once at startup
        tools = await mcp_client.list_tools()
        openai_tools = [mcp_tool_to_openai(t) for t in tools]

        print(f"  Loaded {len(openai_tools)} tools: {[t['function']['name'] for t in openai_tools]}")
        print(f"  LM Studio URL : {args.base_url}")
        print(f"  Model         : {args.model}")
        print("\nType your message and press Enter.  Type 'quit' or 'exit' to stop.\n")

        if args.query:
            # One-shot mode
            print(f"You: {args.query}")
            response = await run_agent(
                args.query, openai_client, mcp_client,
                openai_tools, args.model, args.max_iterations, verbose=args.verbose,
            )
            print(f"\nAssistant: {response}\n")
            return

        # Interactive REPL
        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye.")
                break

            if not user_input:
                continue
            if user_input.lower() in {"quit", "exit", "q"}:
                print("Goodbye.")
                break

            print()  # blank line before response
            try:
                response = await run_agent(
                    user_input, openai_client, mcp_client,
                    openai_tools, args.model, args.max_iterations, verbose=args.verbose,
                )
                print(f"Assistant: {response}\n")
            except Exception as exc:
                print(f"[error] {exc}\n")
                print("       Make sure LM Studio is running and the server is started.")
                print(f"       Expected address: {args.base_url}\n")
