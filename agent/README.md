# Agent Module

## Table of Contents

- [What This Is](#what-this-is)
- [Why It Exists Separately](#why-it-exists-separately)
- [How It Works](#how-it-works)
- [BigQuery Integration](#bigquery-integration)
  - [Available BigQuery Tools](#available-bigquery-tools)
  - [Changes Made for BigQuery](#changes-made-for-bigquery)
  - [Recommended Workflow](#recommended-workflow)
- [File Reference](#file-reference)
- [Prerequisites](#prerequisites)
- [Commands](#commands)
- [Example Session](#example-session)

---

## What This Is

This module implements a local LLM agent that connects to the FastMCP server
in-process and uses its tools to answer user questions. It bridges a local
language model (running in LM Studio) with the MCP tool ecosystem -- the model
can call any registered MCP tool (notes, utils, BigQuery) as part of its reasoning.

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

---

## BigQuery Integration

The agent automatically gains `bq_*` tools when `BIGQUERY_PROJECT_ID` is set in `.env`. No code changes required — tools are discovered via MCP's `tools/list` at agent startup.

### Available BigQuery Tools

| Tool | What the agent can do with it |
|---|---|
| `bq_run_query` | Execute read-only SQL queries; agent enforces LIMIT and SELECT-only rules |
| `bq_list_datasets` | Discover available datasets before writing any SQL |
| `bq_list_tables` | List tables with row counts and sizes for a dataset |
| `bq_get_table` | Inspect schema, fill rates, partitioning, and sample rows |
| `bq_vector_search` | Semantic similarity search; empty `query_text` discovers embedding tables |

### Changes Made for BigQuery

| Component | Change |
|---|---|
| `agent/config.py` — `SYSTEM_PROMPT` | Added rules: explore before querying (`bq_list_datasets → bq_list_tables → bq_get_table`), always include `LIMIT`, never write DML/DDL, report `success=false` errors, use `bq_vector_search` with empty text to discover embedding tables |
| Tool discovery | Automatic — `chat_session.py` calls `mcp_client.list_tools()` at startup; `bq_*` tools appear when BigQuery is enabled, are absent when it is not |
| Agent loop / tool converter | No changes — fully BigQuery-agnostic |

### Recommended Workflow

```
1. bq_list_datasets              → discover available datasets
2. bq_list_tables(dataset_id)    → see tables, row counts, sizes
3. bq_get_table(dataset, table)  → inspect schema + sample rows
4. bq_run_query(sql)             → run SELECT with LIMIT
```

---

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
python -m agent.cli --query "List all datasets in my BigQuery project" --verbose
```

## Example Session

### Notes query
```
Connecting to MCP server (in-process)...
  Loaded 9 tools: ['notes_create_note', 'notes_get_note', 'notes_list_notes', ...]
  LM Studio URL : http://localhost:1234/v1
  Model         : local-model

Type your message and press Enter.  Type 'quit' or 'exit' to stop.

You: Create a note called "MCP setup" with body "FastMCP running locally"
  [tool] notes_create_note({"note": {"title": "MCP setup", "body": "FastMCP running locally", "tags": []}})
  [result] {"id": "4", "title": "MCP setup", ...}

Assistant: Done! Note created with ID 4.

You: quit
Goodbye.
```

### BigQuery query (requires BIGQUERY_PROJECT_ID)
```
Connecting to MCP server (in-process)...
  Loaded 14 tools: ['notes_create_note', ..., 'bq_run_query', 'bq_list_datasets', ...]
  LM Studio URL : http://localhost:1234/v1
  Model         : local-model

Type your message and press Enter.  Type 'quit' or 'exit' to stop.

You: What datasets are in my project?
  [tool] bq_list_datasets({})
  [result] {"success": true, "datasets": [{"id": "analytics"}, {"id": "sales"}]}

Assistant: Your project has 2 datasets: analytics and sales.

You: Show the top 5 countries by user count in analytics.users
  [tool] bq_get_table({"dataset_id": "analytics", "table_id": "users"})
  [result] {"success": true, "schema": [...], "sample_rows": [...]}
  [tool] bq_run_query({"query": "SELECT country, COUNT(*) AS n FROM `analytics.users` GROUP BY 1 ORDER BY 2 DESC LIMIT 5"})
  [result] {"success": true, "rows": [...], "row_count": 5}

Assistant: The top 5 countries by user count are ...
```
