# MCP Prototype: Time Server

**Status:** Prototype — read-only, verified  
**Date:** 2026-05-30  
**Server:** `mcp-server-time` (community MCP server)  
**Task:** t_08c68506 — Prototype the first read-only MCP tool  

## Summary

First read-only MCP server prototype using `mcp-server-time` via `uvx`. Provides two tools: `get_current_time` (any timezone) and `convert_time` (between timezones). Zero security risk — read-only, no credentials, no network access to internal systems.

## Tools Available

| Tool | Description | Example |
|------|-------------|---------|
| `get_current_time` | Current time in a timezone | `Europe/London` |
| `convert_time` | Convert time between timezones | `London 12:00 → Tokyo 20:00` |

## Verified Output

```
get_current_time('Europe/London'):
  datetime: 2026-05-30T11:54:14+01:00
  day_of_week: Saturday
  timezone: Europe/London

convert_time('Europe/London', '12:00', 'Asia/Tokyo'):
  London: 2026-05-30T12:00+01:00
  Tokyo:  2026-05-30T20:00+09:00
  diff: +8.0h
```

## Prerequisites

- **MCP SDK** — already installed in Hermes venv at `/home/jellybot/.hermes/hermes-agent/venv/lib/python3.11/site-packages/mcp`
- **uv** — available at `/usr/bin/uv` (v0.11.14)
- **Hermes config** — `~/.hermes/config.yaml`

## Configuration

Add to `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  time:
    command: "uvx"
    args: ["mcp-server-time"]
    timeout: 30
```

After adding, restart the Hermes gateway for the MCP tools to auto-discover:

```bash
hermes gateway restart
```

The tools will appear as `mcp_time_get_current_time` and `mcp_time_convert_time` in all Hermes conversations.

## Test without gateway restart

Run directly from terminal:

```bash
hermes venv python3 -c "
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test():
    params = StdioServerParameters(command='uvx', args=['mcp-server-time'])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print('Tools:', [t.name for t in tools.tools])
            result = await s.call_tool('get_current_time', {'timezone': 'Europe/London'})
            for c in result.content:
                if c.type == 'text':
                    print(c.text)

asyncio.run(test())
"
```

## Safety Assessment

| Concern | Status |
|---------|--------|
| Read-only | ✓ No write/control capabilities |
| Credentials needed | ✓ None |
| Network access | ✓ Only queries public time API |
| Internal system access | ✓ None |
| Hermes env exposure | ✓ Filtered by MCP client (only PATH/HOME/USER/LANG passed) |

## Next Steps

1. Add this config to Hermes `config.yaml` and restart gateway
2. Expand to more useful MCP servers (GitHub, filesystem, home-network ops)
3. Repeat the assessment pattern for each new server: test → verify read-only → document → enable
