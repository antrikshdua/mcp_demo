"""
Math sub-server -- arithmetic and math utilities.
"""

import asyncio

from fastmcp import FastMCP, Context

from schemas.models import MathOp


math_mcp = FastMCP("Math", instructions="Arithmetic and math utilities.")


@math_mcp.tool
def add(op: MathOp) -> float:
    """Add two numbers."""
    return op.a + op.b


@math_mcp.tool
def subtract(op: MathOp) -> float:
    """Subtract b from a."""
    return op.a - op.b


@math_mcp.tool
def multiply(op: MathOp) -> float:
    """Multiply two numbers."""
    return op.a * op.b


@math_mcp.tool
def divide(op: MathOp) -> float:
    """
    Divide a by b.

    Raises ValueError if b is zero.
    """
    if op.b == 0:
        raise ValueError("Cannot divide by zero")
    return op.a / op.b


@math_mcp.tool
async def factorial(n: int, ctx: Context) -> int:
    """
    Compute n! iteratively with progress reporting.

    Args:
        n: Non-negative integer (max 20 for speed).
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    if n > 20:
        raise ValueError("n must be <= 20 to avoid overflow")

    await ctx.info(f"Computing {n}!")
    result = 1
    for i in range(1, n + 1):
        result *= i
        await ctx.report_progress(progress=i, total=n)
        await asyncio.sleep(0)

    await ctx.info(f"{n}! = {result}")
    return result
