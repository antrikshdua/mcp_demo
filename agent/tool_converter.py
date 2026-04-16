"""
Tool conversion -- MCP tool schema -> OpenAI function definition.
"""

from typing import Any


def mcp_tool_to_openai(tool: Any) -> dict:
    """Convert a FastMCP Tool object to an OpenAI tool definition dict."""
    params = tool.inputSchema or {"type": "object", "properties": {}}
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": params,
        },
    }
