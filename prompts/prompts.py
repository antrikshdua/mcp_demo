"""
MCP Prompts -- single-turn and multi-turn prompt templates.
"""

from api.v1.notes import notes_mcp
from api.v1.utils import utils_mcp
from api.v1.math import math_mcp


@notes_mcp.prompt
def summarize_notes_prompt(topic: str) -> str:
    """
    Generate a prompt asking the LLM to summarise notes on a topic.

    Args:
        topic: The topic to summarise.
    """
    return (
        f"You are a helpful assistant. Use the search_notes tool to find notes "
        f"about '{topic}', then write a concise 3-bullet summary of the key points. "
        f"If no notes are found, say so clearly."
    )


@utils_mcp.prompt
def debug_error_prompt(error_type: str, error_message: str, context: str = "") -> str:
    """
    Generate a debugging prompt for the LLM.

    Args:
        error_type: Exception class name (e.g. 'ValueError').
        error_message: The error message string.
        context: Optional surrounding code or description.
    """
    parts = [
        f"I'm seeing a {error_type}: {error_message}",
        f"Context: {context}" if context else "",
        "Please explain what caused this error and suggest the most likely fix.",
    ]
    return "\n\n".join(p for p in parts if p)


@math_mcp.prompt
def math_tutor_prompt(concept: str, skill_level: str = "beginner") -> str:
    """
    Generate a math tutoring prompt.

    Args:
        concept: Math concept to explain (e.g. 'derivatives').
        skill_level: 'beginner', 'intermediate', or 'advanced'.
    """
    return (
        f"Act as a patient math tutor for a {skill_level} student. "
        f"Explain '{concept}' step by step with one worked example. "
        f"Keep the explanation concise and avoid jargon where possible."
    )
