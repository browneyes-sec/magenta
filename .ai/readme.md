# AI Layer — Magenta Infrastructure

This directory defines the **AI infrastructure layer** that powers the Magenta Agentic Framework. It covers the tooling, protocols, compute, and model distribution systems required to run a production multi-agent cybersecurity fabric.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        MAGENTA FRAMEWORK                                 │
│              (Agent Roles · Swarms · Teaming · Decision Logic)          │
├─────────────────────────────────────────────────────────────────────────┤
│                        .ai  INFRASTRUCTURE LAYER                         │
│                                                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ LangChain│ │ Google   │ │   MCP    │ │   A2A    │ │   Agents     │  │
│  │ Observ.  │ │ ADK/SDK  │ │ Protocol │ │ Protocol │ │  Management  │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │  Data    │ │ Compute  │ │  Models  │ │OpenRouter│ │ Vercel API   │  │
│  │ Sources  │ │ / GPU    │ │Distribution│ │ Gateway  │ │ Gateway/OCO  │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
├─────────────────────────────────────────────────────────────────────────┤
│                              SIEM / SOAR / CLOUD                         │
│              (Sentinel · Splunk · Azure · Entra · Defender)             │
└─────────────────────────────────────────────────────────────────────────┘
```

## Layer Components

| Component | File | Function |
|---|---|---|
| **LangChain Observability** | `observability-langchain.md` | LangSmith/LangFuse tracing, LLM call monitoring, chain-of-thought capture |
| **Google ADK** | `google-adk.md` | Agent development kit patterns, structured tool use, delegation |
| **Data Sources** | `data-sources.md` | SIEM, SOAR, IT, threat intel connectivity abstraction |
| **MCP Integration** | `mcp-integration.md` | Model Context Protocol for standardized tool access |
| **Compute / GPU** | `compute-gpu.md` | GPU resources, inference servers, OLLAMA clusters |
| **Models Distribution** | `models-distributed.md` | Distributed model routing, SLM/LLM tier selection, fallback chains |
| **A2A Protocol** | `a2a-protocol.md` | Agent-to-Agent JSON communication framework |
| **Agents Management** | `agents-management.md` | Agent registry, lifecycle, OpenRouter, Vercel API Gateway, Opencode integration |
