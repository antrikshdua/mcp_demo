"""
MCP Resources -- static and URI-templated resources.
"""

import json
import os

from api.v1.utils import utils_mcp
from api.v1.notes import notes_mcp


@utils_mcp.resource("config://server")
def get_server_config() -> str:
    """
    Read-only server configuration exposed as an MCP resource.
    Clients (and LLMs) can read this to understand the server.
    """
    return json.dumps({
        "name": "FastMCP Production Demo",
        "version": "1.0.0",
        "environment": os.getenv("ENV", "development"),
        "features": ["notes", "math", "utils"],
        "max_note_body_length": 10_000,
    })


@notes_mcp.resource("notes://index")
async def all_notes_resource() -> str:
    """
    Static index resource -- directs clients to use list_notes tool for live data.
    """
    return json.dumps({"message": "Use the notes_list_notes tool for live data."})


@notes_mcp.resource("notes://{note_id}")
async def single_note_resource(note_id: str) -> str:
    """
    URI-template resource: clients request notes://notes/<id> and get a stub.
    """
    return json.dumps({
        "id": note_id,
        "message": f"Use notes_get_note tool with note_id={note_id!r} for live data.",
    })
