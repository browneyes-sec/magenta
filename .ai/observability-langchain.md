# LangChain Observability — Magenta AI Layer

**Reference:** LangSmith · LangFuse · OpenTelemetry tracing for multi-agent cybersecurity workflows.

---

## 1. Observability Architecture

Every agent action, LLM call, tool execution, and swarm decision flows through a unified tracing pipeline.

```
Agent → LangChain Callback Handler → LangSmith/LangFuse → Elasticsearch + Azure Monitor
```

### Trace Structure (Per Agent Turn)

```
Trace: mission-8932
├── Span: swarm_manager.decompose
│   ├── LLM Call: ollama/mixtral:8x7b
│   │   ├── Tokens In: 2450
│   │   ├── Tokens Out: 680
│   │   ├── Latency: 3.2s
│   │   └── Model: local-ollama-01
│   └── Output: 5 tasks generated
├── Span: triage_agent.execute
│   ├── LLM Call: ollama/qwen2.5:7b
│   │   ├── Tokens In: 1200
│   │   ├── Tokens Out: 340
│   │   └── Latency: 1.8s
│   ├── Tool Call: sentinel_query_incidents
│   │   ├── Duration: 0.4s
│   │   └── Status: success
│   └── Output: verdict "high_severity_phishing"
└── Span: contain_agent.execute
    ├── Approval Gate: risk_score=72 → human_queue
    └── Status: pending_approval
```

---

## 2. LangSmith Integration

### Setup

```python
from langsmith import Client
from langchain.callbacks import LangSmithCallbackHandler

langsmith = Client(
    api_key=os.getenv("LANGSMITH_API_KEY"),
    project_name="magenta-prod"
)

# Attach to agent
tracer = LangSmithCallbackHandler(
    project_name="magenta-prod",
    tags=["agent:swarm_manager", "mission:8932"]
)
```

### Agent-Level Tracing

```python
class ObservableAgent:
    def __init__(self, config: AgentConfig):
        self.tracer = LangSmithCallbackHandler(
            project_name="magenta",
            tags=[f"agent:{config.role}", f"model:{config.model}"]
        )

    async def execute(self, task: Task) -> Result:
        with self.tracer.as_trace(
            name=f"{self.config.role}.execute",
            inputs={"task_id": task.id, "alert_id": task.alert_id}
        ):
            # LLM call
            response = await self.llm.ainvoke(
                self.build_prompt(task),
                callbacks=[self.tracer]
            )

            # Tool call
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    with self.tracer.as_span(f"tool:{tool_call.name}"):
                        result = await self.execute_tool(tool_call)
                        self.tracer.add_outputs({"result": str(result)[:500]})

            return response
```

---

## 3. LangFuse Integration (Open Source Alternative)

```python
from langfuse import Langfuse
from langfuse.callback import CallbackHandler

langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
)

handler = CallbackHandler(
    trace_name="magenta-swarm",
    user_id="swarm-manager-v1",
    session_id="mission-8932",
    metadata={"env": "prod", "pipeline": "phishing-triage"}
)
```

---

## 4. Key Metrics

| Metric | Source | Alert Threshold |
|---|---|---|
| LLM latency (p95) | LangSmith | > 10s → warn, > 30s → page |
| Token cost per mission | LangSmith | > $0.05/mission → review model tier |
| Tool call error rate | LangSmith | > 5% → page |
| Agent loop count | LangSmith | > 15 turns → possible hallucination |
| Idempotency hit rate | Custom | < 50% → possible duplicate injection |
| Consensus agreement score | Custom | < 0.6 → review model selection |
| Swarm completion rate | Custom | < 90% → investigate agent failures |

---

## 5. OpenTelemetry Export

All traces export to Azure Monitor for unified SOC observability:

```python
from opentelemetry import trace
from opentelemetry.exporter.azure_monitor import AzureMonitorTraceExporter

exporter = AzureMonitorTraceExporter(
    connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
)
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(exporter)
)
```

---

## 6. LangGraph Integration (For Complex State Machines)

For agents that require persistent state across turns (e.g., Investigation Agent building a timeline), LangGraph provides cyclic graph execution with built-in tracing:

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint import MemorySaver

# Define agent state machine
graph = StateGraph(InvestigationState)
graph.add_node("collect_evidence", collect_agent)
graph.add_node("analyze_iocs", analyze_agent)
graph.add_node("build_timeline", timeline_agent)
graph.set_entry_point("collect_evidence")
graph.add_conditional_edges(
    "analyze_iocs",
    lambda state: "build_timeline" if state.iocs_found else END
)

# LangSmith traces every node transition
app = graph.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["human_review"]
)
```
