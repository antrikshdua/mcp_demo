"""
Agent loop -- core LLM + tool-calling loop.
"""

from __future__ import annotations

import json

from openai import AsyncOpenAI
from fastmcp import Client

from .config import SYSTEM_PROMPT


async def run_agent(
    user_message: str,
    openai_client: AsyncOpenAI,
    mcp_client: Client,
    openai_tools: list[dict],
    model: str,
    max_iterations: int,
    verbose: bool = False,
) -> str:
    """
    Run one turn of the agent loop.

    Sends user_message to the LLM with the full tool list.  When the model
    requests tool calls, executes them via the MCP client and appends the
    results.  Loops until the model returns a plain-text message or the
    iteration cap is hit.

    Returns the final assistant text response.
    """
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    for iteration in range(max_iterations):
        response = await openai_client.chat.completions.create(
            model=model,
            messages=messages,
            tools=openai_tools if openai_tools else None,
            tool_choice="auto" if openai_tools else None,
        )

        choice = response.choices[0]
        assistant_msg = choice.message

        # No tool calls -- model produced a final answer
        if not assistant_msg.tool_calls:
            return assistant_msg.content or ""

        # Append the assistant's tool-call request to the message history
        messages.append({
            "role": "assistant",
            "content": assistant_msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in assistant_msg.tool_calls
            ],
        })

        # Execute every tool call the model requested (may be multiple)
        for tc in assistant_msg.tool_calls:
            tool_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}

            if verbose:
                print(f"  [tool] {tool_name}({json.dumps(args, separators=(',', ':'))})")

            # Call the tool via the in-process MCP client
            try:
                result = await mcp_client.call_tool(tool_name, args)
                # Extract text from the result content
                if result.content:
                    tool_output = result.content[0].text
                elif result.structured_content:
                    sc = result.structured_content
                    tool_output = json.dumps(sc.get("result", sc))
                else:
                    tool_output = ""
            except Exception as exc:
                tool_output = f"Error: {exc}"

            if verbose:
                preview = tool_output[:120] + "..." if len(tool_output) > 120 else tool_output
                print(f"  [result] {preview}")

            # Append the tool result so the model can read it
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_output,
            })

    # Iteration cap reached -- ask the model to summarize with what it has
    messages.append({
        "role": "user",
        "content": "Please summarize what you found so far.",
    })
    final = await openai_client.chat.completions.create(
        model=model,
        messages=messages,
    )
    return final.choices[0].message.content or "(no response)"
