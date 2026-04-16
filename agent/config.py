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
    "After calling tools, summarize the results clearly for the user."
)
