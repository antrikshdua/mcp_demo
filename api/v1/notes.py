"""
Notes sub-server -- create, read, search, and delete notes.
"""

from datetime import datetime, timezone

from fastmcp import FastMCP, Context

from schemas.models import NoteCreate, NoteResult, SearchQuery
from core.lifespan import AppState


notes_mcp = FastMCP("Notes", instructions="Create, read, and search notes.")


@notes_mcp.tool(tags={"write"})
async def create_note(note: NoteCreate, ctx: Context) -> dict:
    """
    Create a new note and persist it in the in-memory store.

    Returns the created note with its generated ID.
    """
    state: AppState = ctx.request_context.lifespan_context

    note_id = str(len(state.notes_db) + 1)
    result = NoteResult(
        id=note_id,
        title=note.title,
        body=note.body,
        tags=note.tags,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    state.notes_db[note_id] = result
    await ctx.info(f"Created note id={note_id}: {note.title!r}")
    return result.model_dump()


@notes_mcp.tool(tags={"read"})
async def get_note(note_id: str, ctx: Context) -> dict:
    """
    Retrieve a note by its ID.

    Raises a KeyError if the note does not exist.
    """
    state: AppState = ctx.request_context.lifespan_context
    if note_id not in state.notes_db:
        raise KeyError(f"Note '{note_id}' not found")
    await ctx.debug(f"Fetched note id={note_id}")
    return state.notes_db[note_id].model_dump()


@notes_mcp.tool(tags={"read"})
async def search_notes(query: SearchQuery, ctx: Context) -> list[dict]:
    """
    Search notes by text and optional tag filter.

    Returns up to `limit` results ranked by relevance (substring match).
    """
    state: AppState = ctx.request_context.lifespan_context
    await ctx.info(f"Searching notes for {query.query!r} (limit={query.limit})")

    results = []
    for note in state.notes_db.values():
        text_match = (
            query.query.lower() in note.title.lower()
            or query.query.lower() in note.body.lower()
        )
        tag_match = not query.tags or any(t in note.tags for t in query.tags)
        if text_match and tag_match:
            results.append(note)

    results = results[: query.limit]
    await ctx.info(f"Found {len(results)} matching notes")
    return [n.model_dump() for n in results]


@notes_mcp.tool(tags={"write", "admin"})
async def delete_note(note_id: str, ctx: Context) -> dict:
    """
    Delete a note permanently.

    Requires admin privileges in production (enforced via auth middleware).
    """
    state: AppState = ctx.request_context.lifespan_context
    if note_id not in state.notes_db:
        raise KeyError(f"Note '{note_id}' not found")
    del state.notes_db[note_id]
    await ctx.warning(f"Deleted note id={note_id}")
    return {"deleted": True, "id": note_id}


@notes_mcp.tool(tags={"read"})
async def list_notes(ctx: Context) -> list[dict]:
    """Return all notes in the store."""
    state: AppState = ctx.request_context.lifespan_context
    return [n.model_dump() for n in state.notes_db.values()]
