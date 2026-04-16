"""
Utils sub-server -- general utility tools.
"""

import asyncio
from datetime import datetime, timezone

import httpx
from fastmcp import FastMCP, Context

from core.lifespan import AppState


utils_mcp = FastMCP("Utils", instructions="General utility tools.")


@utils_mcp.tool
def echo(message: str) -> str:
    """Echo the message back. Useful for testing connectivity."""
    return message


@utils_mcp.tool
def server_time() -> dict:
    """Return the current UTC server time."""
    now = datetime.now(timezone.utc)
    return {
        "iso": now.isoformat(),
        "timestamp": now.timestamp(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
    }


@utils_mcp.tool
async def http_get(url: str, ctx: Context) -> dict:
    """
    Perform an HTTP GET request and return status + first 500 chars of body.

    Do NOT use for internal/private network addresses in production.
    """
    state: AppState = ctx.request_context.lifespan_context
    await ctx.info(f"GET {url}")

    try:
        resp = await state.http_client.get(url)
        body_preview = resp.text[:500] if resp.text else ""
        await ctx.info(f"Response: HTTP {resp.status_code}")
        return {
            "status_code": resp.status_code,
            "ok": resp.is_success,
            "content_type": resp.headers.get("content-type", ""),
            "body_preview": body_preview,
        }
    except httpx.TimeoutException:
        raise TimeoutError(f"Request to {url} timed out after 10s")
    except httpx.RequestError as exc:
        raise ConnectionError(f"Failed to reach {url}: {exc}")


@utils_mcp.tool
async def process_items(
    items: list[str],
    ctx: Context,
    uppercase: bool = False,
) -> list[str]:
    """
    Process a list of items with live progress reporting.

    Args:
        items: List of strings to process.
        uppercase: If True, convert each item to uppercase.
    """
    await ctx.info(f"Processing {len(items)} items (uppercase={uppercase})")
    results = []
    for i, item in enumerate(items):
        await ctx.report_progress(progress=i, total=len(items))
        processed = item.upper() if uppercase else item.strip()
        results.append(processed)
        await asyncio.sleep(0)

    await ctx.info("Processing complete")
    return results
