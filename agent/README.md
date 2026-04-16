# Agent Module

## What This Is

This module implements a local LLM agent that connects to the FastMCP server
in-process and uses its tools to answer user questions. It bridges a local
language model (running in LM Studio) with the MCP tool ecosystem -- the model
can call any registered MCP tool (math, notes, utils) as part of its reasoning.

## Why It Exists Separately

The agent is a consumer of the MCP server, not part of it. Keeping it in its
own module means:

- The MCP server can run standalone (STDIO or HTTP) without any LLM dependency.
- The agent can be swapped, extended, or replaced without touching server code.
- Different agents (CLI, web UI, Slack bot) can all import from `agent/` and
  reuse the same loop and tool conversion logic.

## How It Works

1. `cli.py` parses arguments and calls `create_server()` to build the MCP
   server instance.
2. `chat_session.py` opens an in-process `fastmcp.Client` against that server
   and discovers all available tools at startup.
3. `tool_converter.py` converts each MCP tool schema into the OpenAI
   function-calling format that LM Studio expects.
4. For each user message, `agent_loop.py` sends it to the LLM along with the
   tool definitions. When the model requests a tool call, the loop executes it
   via the MCP client, appends the result, and sends the updated conversation
   back to the model. This repeats until the model produces a plain-text answer
   or the iteration cap is reached.
5. `config.py` holds all defaults (base URL, model name, system prompt) in one
   place.

## File Reference

| File | Purpose |
|---|---|
| `config.py` | Defaults: LM Studio URL, API key, model name, max iterations, system prompt |
| `tool_converter.py` | `mcp_tool_to_openai()` -- converts MCP tool schemas to OpenAI function definitions |
| `agent_loop.py` | `run_agent()` -- the core loop that alternates between LLM calls and tool execution |
| `chat_session.py` | `chat_session()` -- interactive REPL and one-shot query mode |
| `cli.py` | CLI entry point -- argument parsing and startup |

## Prerequisites

- LM Studio installed and running with a model that supports function/tool
  calling loaded on its local server (default: `http://localhost:1234/v1`).
- Recommended models (search these in LM Studio):
  - `lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF` (Q4_K_M) -- best overall
  - `NousResearch/Hermes-2-Pro-Llama-3-8B-GGUF` (Q4_K_M) -- best for tool calling
  - `lmstudio-community/Phi-3.5-mini-instruct-GGUF` (Q4) -- low VRAM
  - `lmstudio-community/Qwen2.5-14B-Instruct-GGUF` (Q4_K_M) -- high-end GPU

## Commands

All commands assume you are in the `mcp_tooling_modular/` directory with the
virtual environment activated:

```bash
source .venv/Scripts/activate
```

**Interactive chat (default):**

```bash
python -m agent.cli
```

**One-shot query:**

```bash
python -m agent.cli --query "What is 12 factorial?"
```

**Specify a model:**

```bash
python -m agent.cli --model "lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF"
```

**Point to a different LM Studio address:**

```bash
python -m agent.cli --base-url http://localhost:1234/v1
```

**Limit tool call iterations per turn:**

```bash
python -m agent.cli --max-iterations 5
```

**Verbose mode (prints each tool call and raw result):**

```bash
python -m agent.cli --verbose
```

**Combine flags:**

```bash
python -m agent.cli --query "Add 987 and 654, then multiply by 3" --verbose
```

## Example Session

```
Connecting to MCP server (in-process)...
  Loaded 14 tools: ['math_add', 'math_subtract', ...]
  LM Studio URL : http://localhost:1234/v1
  Model         : local-model

Type your message and press Enter.  Type 'quit' or 'exit' to stop.

You: What is 15 factorial?
  [tool] math_factorial({"n":15})
  [result] 1307674368000