"""
In-process demo -- exercises every tool, resource, and prompt without a running server.
"""

from __future__ import annotations

import asyncio
import json

from fastmcp import Client


async def run_demo(mcp) -> None:
    """
    Connects to the server in-process (no network) and exercises
    every tool, resource, and prompt.
    """
    print("\n" + "=" * 60)
    print("  FastMCP In-Process Demo")
    print("=" * 60)

    async with Client(mcp) as client:

        # -- List everything ----------------------------------------
        tools     = await client.list_tools()
        resources = await client.list_resources()
        templates = await client.list_resource_templates()
        prompts   = await client.list_prompts()

        print(f"\n[tools]     {[t.name for t in tools]}")
        print(f"[resources] {[str(r.uri) for r in resources]}")
        print(f"[templates] {[str(t.uriTemplate) for t in templates]}")
        print(f"[prompts]   {[p.name for p in prompts]}")

        # -- Notes tools -------------------------------------------
        print("\n-- Notes --------------------------------------------")

        r = await client.call_tool("notes_list_notes", {})
        raw_notes = json.loads(r.content[0].text)
        print(f"  list_notes()        = {len(raw_notes)} notes seeded at startup")

        r = await client.call_tool("notes_create_note", {
            "note": {"title": "Test Note", "body": "Created during demo run.", "tags": ["demo"]}
        })
        created = json.loads(r.content[0].text)
        print(f"  create_note()       = id={created['id']!r}, title={created['title']!r}")

        r = await client.call_tool("notes_get_note", {"note_id": "1"})
        print(f"  get_note('1')       = {json.loads(r.content[0].text)['title']!r}")

        r = await client.call_tool("notes_search_notes", {
            "query": {"query": "MCP", "limit": 5}
        })
        print(f"  search_notes('MCP') = {len(json.loads(r.content[0].text))} result(s)")

        r = await client.call_tool("notes_delete_note", {"note_id": created["id"]})
        print(f"  delete_note({created['id']!r})    = {json.loads(r.content[0].text)}")

        # get a deleted note -- expect error
        try:
            await client.call_tool("notes_get_note", {"note_id": created["id"]})
        except Exception as exc:
            print(f"  get deleted note    -> Error (expected): {exc}")

        # -- Utils tools -------------------------------------------
        print("\n-- Utils --------------------------------------------")

        r = await client.call_tool("utils_echo", {"message": "Hello, MCP!"})
        print(f"  echo()              = {r.content[0].text!r}")

        r = await client.call_tool("utils_server_time", {})
        print(f"  server_time()       = {json.loads(r.content[0].text)['iso']}")

        r = await client.call_tool("utils_process_items", {
            "items": ["  hello  ", "  world  "], "uppercase": True,
        })
        print(f"  process_items()     = {json.loads(r.content[0].text)}")

        # -- Resources ---------------------------------------------
        print("\n-- Resources ----------------------------------------")

        r = await client.read_resource("config://utils/server")
        config = json.loads(r[0].text)
        print(f"  config://utils/server = {config}")

        r = await client.read_resource("notes://notes/42")
        print(f"  notes://notes/42      = {r[0].text[:80]}...")

        # -- Prompts -----------------------------------------------
        print("\n-- Prompts ------------------------------------------")

        r = await client.get_prompt("notes_summarize_notes_prompt", {"topic": "MCP"})
        print(f"  summarize_notes_prompt preview: {r.messages[0].content.text[:80]}...")

        r = await client.get_prompt("utils_debug_error_prompt", {
            "error_type": "KeyError", "error_message": "note not found",
        })
        print(f"  debug_error_prompt preview: {r.messages[0].content.text[:80]}...")

    print("\n" + "=" * 60)
    print("  Demo complete -- all systems nominal.")
    print("=" * 60 + "\n")
