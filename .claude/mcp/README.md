# Second Brain MCP Server

FastMCP stdio server exposing Henry's Second Brain memory to external AI agents.
**All writes are proposal-only — nothing lands in memory without Henry's approval.**

## Tools

| Tool | Description |
|------|-------------|
| `search_memory` | Semantic search over the memory vault |
| `list_categories` | List valid memory categories |
| `get_recent_daily_logs` | Fetch daily log content for the last N days |
| `propose_memory_fact` | Queue a new memory fact for Henry's review |
| `log_agent_session` | Queue an agent session log for Henry's review |

## Claude Code / Claude Agent SDK (settings.json or settings.local.json)

Add to `mcpServers` in `~/.claude/settings.json` or the project's `.claude/settings.local.json`:

```json
{
  "mcpServers": {
    "second-brain": {
      "command": "C:\\Users\\cliao\\Desktop\\2nd_Brain\\.claude\\venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\cliao\\Desktop\\2nd_Brain\\.claude\\mcp\\second_brain_server.py"]
    }
  }
}
```

## Cursor

Add to `~/.cursor/mcp.json` (or the workspace `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "second-brain": {
      "command": "C:\\Users\\cliao\\Desktop\\2nd_Brain\\.claude\\venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\cliao\\Desktop\\2nd_Brain\\.claude\\mcp\\second_brain_server.py"]
    }
  }
}
```

## Claude Agent SDK (Python)

```python
from anthropic import Anthropic
from anthropic.beta.mcp import stdio_client, StdioServerParameters

server = StdioServerParameters(
    command=r"C:\Users\cliao\Desktop\2nd_Brain\.claude\venv\Scripts\python.exe",
    args=[r"C:\Users\cliao\Desktop\2nd_Brain\.claude\mcp\second_brain_server.py"],
)

async with stdio_client(server) as (read, write):
    # pass read/write to your agent session
    ...
```

## Security

- `propose_memory_fact` and `log_agent_session` write to `vault/drafts/proposals/` only.
- Henry reviews and approves each proposal before it enters the memory database.
- No agent can write directly to `memory.sqlite` or vault files.
