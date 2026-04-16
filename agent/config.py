"""
Agent configuration -- defaults, system prompt, constants.
"""

DEFAULT_BASE_URL = "http://localhost:1234/v1"
# LM Studio does not require an API key, but the openai library needs a
# non-empty string.  "lm-studio" is the conventional placeholder.
DEFAULT_API_KEY = "lm-studio"
# Pass "default" to let LM Studio use whichever model is currently loaded.
# Or copy the exact model identifier shown in the LM Studio UI.
DEFAULT_MODEL = "local-model"
DEFAULT_MAX_ITERATIONS = 10

SYSTEM_PROMPT = (
    "You are a helpful assistant with access to a set of tools. "
    "Use the tools whenever they would help answer the user's question. "
    "Always prefer using a tool over guessing when factual data is needed. "
    "After calling tools, summarize the results clearly for the user.\n\n"
    "BigQuery tools (prefixed bq_) are available when configured:\n"
    "- Always explore with bq_list_datasets → bq_list_tables → bq_get_table before writing SQL.\n"
    "- Always include a LIMIT clause in every SQL query (start with LIMIT 20).\n"
    "- Never write INSERT, UPDATE, DELETE, DROP, or any data-modifying SQL.\n"
    "- Use bq_vector_search with empty query_text to discover embedding tables.\n"
    "- If a bq_ tool returns success=false, report the error message to the user."
)
