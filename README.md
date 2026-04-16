# MCP Tooling Demo

## What This Is

A production-grade Model Context Protocol (MCP) server built with FastMCP,
split into a maintainable modular structure. It exposes tools, resources, and
prompts that any MCP-compatible client can consume -- Claude Desktop, Cursor,
custom agents, or the included LLM agent.

The server provides three domains of functionality:

- **Math** -- arithmetic operations and factorial with progress reporting.
- **Notes** -- in-memory CRUD note store with search and tag filtering.
- **Utils** -- echo, server time, HTTP GET proxy, and batch item processing.

Each domain runs as a sub-server, mounted onto a single main server with
namespace prefixes (`math_`, `notes_`, `utils_`).

## Why Run the Server Separately

The MCP server is the tool provider. It can operate in two modes:

1. **STDIO mode** -- the server communicates over stdin/stdout. This is how
   Claude Desktop and Cursor connect to MCP servers. No port, no network -- the
   MCP client spawns the server as a subprocess and talks to it directly.

2. **HTTP mode** -- the server listens on a port and exposes a streamable HTTP
   endpoint at `/mcp`. This is for remote clients, web applications, load-balanced
   deployments, or any client that connects over the network.

Running the server separately means:

- Multiple clients can connect to one server instance (HTTP mode).
- The server stays up even when a client disconnects.
- You can add health checks, metrics, and readiness probes for orchestrators
  like Kubernetes.
- You can develop and test tools without needing an LLM -- use `--demo` to
  exercise every tool, resource, and prompt in-process.

The included `agent/` module demonstrates the alternative: connecting to the
server in-process (no network, no subprocess) for local development and
single-user use.

## Project Structure

```
mcp_tooling_modular/
|-- main.py                 Entry point (argparse, server startup, demo)
|-- server.py               Server composition (mounts, middleware, auth)
|-- lifespan.py             AppState dataclass and startup/shutdown lifecycle
|-- demo.py                 In-process smoke test for all capabilities
|-- requirements.txt        Python dependencies
|-- schemas/
|   |-- __init__.py
|   |-- models.py           Pydantic models (NoteCreate, MathOp, SearchQuery, etc.)
|-- middlewares/
|   |-- __init__.py
|   |-- audit.py            AuditMiddleware, RequestCounterMiddleware
|-- api/
|   |-- __init__.py
|   |-- routes.py           Custom HTTP routes (/health, /ready, /metrics)
|   |-- v1/
|       |-- __init__.py
|       |-- math.py         Math sub-server (add, subtract, multiply, divide, factorial)
|       |-- notes.py        Notes sub-server (create, get, search, delete, list)
|       |-- utils.py        Utils sub-server (echo, server_time, http_get, process_items)
|-- resources/
|   |-- __init__.py
|   |-- resources.py        MCP resources (config://server, notes://index, notes://{id})
|-- prompts/
|   |-- __init__.py
|   |-- prompts.py          MCP prompts (summarize_notes, debug_error, math_tutor)
|-- agent/
    |-- __init__.py
    |-- config.py           Agent defaults and system prompt
    |-- tool_converter.py   MCP-to-OpenAI tool schema conversion
    |-- agent_loop.py       Core LLM + tool-calling loop
    |-- chat_session.py     Interactive REPL and one-shot mode
    |-- cli.py              Agent CLI entry point
    |-- README.md           Agent-specific documentation
```

## Setup

```bash
cd mcp_tooling_modular
python -m venv .venv
source .venv/Scripts/activate    # Windows (Git Bash / MSYS2)
# source .venv/bin/activate      # macOS / Linux
pip install -r requirements.txt
```

## Server Commands

All commands assume you are in `mcp_tooling_modular/` with the venv activated.

**Run the in-process demo (no server, no network -- tests all tools, resources, prompts):**

```bash
python main.py --demo
```

Expected output ends with:

```
============================================================
  Demo complete -- all systems nominal.
============================================================
```

**Run as STDIO server (for Claude Desktop, Cursor, or any MCP client that spawns a subprocess):**

```bash
python main.py
```

To configure in Claude Desktop, add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "production-demo": {
      "command": "python",
      "args": ["path/to/mcp_tooling_modular/main.py"]
    }
  }
}
```

**Run as HTTP server:**

```bash
python main.py --http
```

This starts the server on `http://127.0.0.1:8000` with:

- MCP endpoint: `http://127.0.0.1:8000/mcp`
- Health check: `http://127.0.0.1:8000/health`
- Readiness probe: `http://127.0.0.1:8000/ready`
- Metrics: `http://127.0.0.1:8000/metrics`

**Run on a custom host and port:**

```bash
python main.py --http --host 0.0.0.0 --port 9000
```

**Verify endpoints with curl:**

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}

curl http://127.0.0.1:8000/ready
# {"status":"ready","server":"ProductionDemoServer","version":"1.0.0"}

curl http://127.0.0.1:8000/metrics
# {"uptime_note":"see started_at in lifespan state","endpoint":"/metrics"}
```

## Agent Commands

The agent connects to the MCP server in-process and uses a local LLM (via LM
Studio) to answer questions with tool calls. See `agent/README.md` for full
documentation.

```bash
python -m agent.cli                                    # interactive chat
python -m agent.cli --query "What is 12 factorial?"    # one-shot
python -m agent.cli --verbose                          # show tool calls
```

## Available Tools

After mounting, tools are prefixed with their namespace:

| Tool | Description |
|---|---|
| `math_add` | Add two numbers |
| `math_subtract` | Subtract b from a |
| `math_multiply` | Multiply two numbers |
| `math_divide` | Divide a by b (errors on zero) |
| `math_factorial` | Compute n! with progress reporting |
| `notes_create_note` | Create a note with title, body, tags |
| `notes_get_note` | Retrieve a note by ID |
| `notes_search_notes` | Search notes by text and tag filter |
| `notes_delete_note` | Delete a note permanently |
| `notes_list_notes` | List all notes |
| `utils_echo` | Echo a message back |
| `utils_server_time` | Current UTC server time |
| `utils_http_get` | HTTP GET with status and body preview |
| `utils_process_items` | Batch process strings with progress |

## Available Resources

| URI | Description |
|---|---|
| `config://utils/server` | Server configuration (name, version, features) |
| `notes://notes/index` | Notes index stub |
| `notes://notes/{note_id}` | Single note stub (URI template) |

## Available Prompts

| Prompt | Description |
|---|---|
| `notes_summarize_notes_prompt` | Summarise notes on a given topic |
| `utils_debug_error_prompt` | Debug an error with context |
| `math_math_tutor_prompt` | Explain a math concept step by step |
