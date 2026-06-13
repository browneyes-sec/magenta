# MCP Integration — Magenta AI Layer

**Model Context Protocol (MCP)** provides standardized tool access for AI agents. Magenta uses MCP as the universal tool gateway across all agent roles.

---

## 1. MCP Architecture

```
Agent
  │
  ├──► MCP Client (in-agent)
  │         │
  │         ├──► MCP Server: Sentinel
  │         │       ├─── sentinel_query_incidents
  │         │       ├─── sentinel_update_incident
  │         │       └─── sentinel_get_alert_details
  │         │
  │         ├──► MCP Server: Entra ID
  │         │       ├─── entra_disable_account
  │         │       ├─── entra_get_user_info
  │         │       └─── entra_list_group_members
  │         │
  │         ├──► MCP Server: Defender ATP
  │         │       ├─── defender_isolate_host
  │         │       ├─── defender_run_scan
  │         │       └─── defender_get_alerts
  │         │
  │         ├──► MCP Server: Data Lake
  │         │       ├─── lake_write_evidence
  │         │       └─── lake_query_events
  │         │
  │         └──► MCP Server: Registry
  │                 ├─── registry_write_activity
  │                 └─── registry_query_activity
  │
  └──► (more agents with their own MCP client instances)
```

---

## 2. MCP Server Definitions

### Sentinel MCP Server

```python
# sentinel_mcp_server.py
from mcp.server import Server
from mcp.types import Tool, TextContent

server = Server("magenta-sentinel")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="sentinel_query_incidents",
            description="Query Sentinel incidents with KQL filter",
            inputSchema={
                "type": "object",
                "properties": {
                    "kql_filter": {"type": "string"},
                    "max_results": {"type": "integer", "default": 50}
                },
                "required": ["kql_filter"]
            }
        ),
        Tool(
            name="sentinel_update_incident",
            description="Update Sentinel incident status/severity/owner",
            inputSchema={
                "type": "object",
                "properties": {
                    "incident_id": {"type": "string"},
                    "status": {"type": "string", "enum": ["Active", "Closed"]},
                    "comment": {"type": "string"}
                },
                "required": ["incident_id"]
            }
        ),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "sentinel_query_incidents":
        result = await sentinel_client.query(
            f"SecurityIncident | where {arguments['kql_filter']}"
            f" | take {arguments.get('max_results', 50)}"
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    elif name == "sentinel_update_incident":
        result = await sentinel_client.update_incident(
            arguments["incident_id"],
            arguments.get("status"),
            arguments.get("comment")
        )
        return [TextContent(type="text", text=json.dumps(result))]
```

### Entra ID MCP Server

```python
server = Server("magenta-entra-id")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="entra_disable_account",
            description="Disable a user account in Entra ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_principal_name": {"type": "string"},
                    "reason": {"type": "string", "enum": ["compromised", "malicious", "policy"]}
                },
                "required": ["user_principal_name", "reason"]
            }
        ),
    ]
```

---

## 3. Agent-to-MCP Binding

Agents discover available MCP servers at startup:

```yaml
agent_mcp_binding:
  triage_agent:
    mcp_servers:
      - "magenta-sentinel"
      - "magenta-registry"
  containment_agent:
    mcp_servers:
      - "magenta-entra-id"
      - "magenta-defender"
      - "magenta-sentinel"
      - "magenta-registry"
  enrich_agent:
    mcp_servers:
      - "magenta-sentinel"
      - "magenta-threat-intel"
      - "magenta-servicenow"
      - "magenta-data-lake"
```

---

## 4. MCP Client in Agent

```python
class MCPAgentClient:
    def __init__(self, agent_config: AgentConfig):
        self.sessions = {}
        for server_name in agent_config.mcp_servers:
            self.sessions[server_name] = await self.connect(server_name)

    async def connect(self, server_name: str) -> ClientSession:
        # MCP over stdio or HTTP
        if MCP_SERVERS[server_name].transport == "stdio":
            process = await run_server(MCP_SERVERS[server_name].command)
            return ClientSession(process.stdout, process.stdin)
        else:
            return ClientSession(
                HTTPTransport(MCP_SERVERS[server_name].url)
            )

    async def call_tool(self, server: str, tool: str, args: dict) -> str:
        session = self.sessions[server]
        result = await session.call_tool(tool, args)
        return result.content[0].text
```

---

## 5. MCP Security

| Concern | Control |
|---|---|
| Tool authorization | Agent's managed identity scoped to specific MCP tools |
| Parameter validation | JSON Schema enforced at MCP server boundary |
| Audit | Every tool call logged to Registry Agent |
| Rate limiting | MCP server enforces per-agent rate limits |
| Timeout | Tool execution capped at 30s; longer = circuit break |
| Input sanitization | MCP server strips control characters, limits payload size |

---

## 6. MCP Tool Catalog (Cybersecurity)

| MCP Server | Tools |
|---|---|
| `magenta-sentinel` | query_incidents, update_incident, get_alert, run_kql |
| `magenta-splunk` | search_jobs, get_results, list_fired_alerts |
| `magenta-entra-id` | disable_account, get_user, list_group, get_signin_logs |
| `magenta-defender` | isolate_host, run_scan, get_alerts, list_devices |
| `magenta-servicenow` | create_ticket, update_ticket, query_cmdb |
| `magenta-threat-intel` | scan_url, scan_hash, get_ip_reputation, get_domain_info |
| `magenta-data-lake` | write_evidence, query_events, get_schema |
| `magenta-registry` | write_activity, query_activity, get_mission_status |
| `magenta-notify` | send_email, send_slack, send_teams, create_page |
