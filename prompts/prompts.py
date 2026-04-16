"""
MCP Prompts -- single-turn and multi-turn prompt templates.
"""

from api.v1.notes import notes_mcp
from api.v1.utils import utils_mcp
from api.v1.bigquery import bigquery_mcp


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


@bigquery_mcp.prompt
def bq_query_builder_prompt(goal: str, dataset_hint: str = "") -> str:
    """Generate a prompt that guides the LLM to explore BigQuery and write a safe SELECT query.

    Args:
        goal: What the user wants to find or compute.
        dataset_hint: Optional dataset name to scope the search.
    """
    hint = f" Focus on the '{dataset_hint}' dataset." if dataset_hint else ""
    return (
        f"You are a BigQuery analyst with access to bq_list_datasets, bq_list_tables, "
        f"bq_get_table, and bq_run_query tools.{hint}\n\n"
        f"Goal: {goal}\n\n"
        "Steps:\n"
        "1. Use bq_list_datasets (or bq_list_tables if you already know the dataset) to orient yourself.\n"
        "2. Use bq_get_table to inspect schemas and fill-rates before writing SQL.\n"
        "3. Write a SELECT query with a LIMIT clause (start with LIMIT 20).\n"
        "4. Execute with bq_run_query and summarise the results clearly.\n"
        "Never use INSERT, UPDATE, DELETE, DROP, or any data-modifying statement."
    )


@bigquery_mcp.prompt
def bq_schema_explorer_prompt(dataset_id: str) -> str:
    """Generate a prompt to fully document a BigQuery dataset schema.

    Args:
        dataset_id: The BigQuery dataset ID to explore.
    """
    return (
        f"You are a data engineer. Use bq_list_tables and bq_get_table to fully document "
        f"the '{dataset_id}' BigQuery dataset.\n\n"
        "For each table, return:\n"
        "- Table name and type (TABLE / VIEW / PARTITIONED_TABLE)\n"
        "- Row count and approximate size\n"
        "- Partition field (if any) and whether a partition filter is required\n"
        "- Primary key columns (if defined)\n"
        "- Schema with column types, modes, and fill-rates\n"
        "Present the output as a structured Markdown report."
    )
