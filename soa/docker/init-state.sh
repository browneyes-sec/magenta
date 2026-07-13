#!/usr/bin/env bash
# Magenta ASOAR — State Initialization Script
# Registers base agents, instantiates Dictator, and creates a sample mission.
# Run after core services are up: docker exec magenta-api bash /init-state.sh
set -euo pipefail

echo "=== Magenta State Initialization ==="
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

# ── 1. Register base agents ──────────────────────────────
echo ">>> Registering base agents in SQLite..."
python3 -c "
import asyncio
from magenta.core.agent import agent_registry
from magenta.core.models import AgentConfig

async def register_agents():
    agents = [
        AgentConfig(agent_id='triage-001', role='triage', model_provider='ollama', model_name='qwen2.5:0.5b', instructions='Triage incoming alerts and assign severity.'),
        AgentConfig(agent_id='enrich-001', role='enrichment', model_provider='ollama', model_name='qwen2.5:0.5b', instructions='Gather context and threat intel for alerts.'),
        AgentConfig(agent_id='contain-001', role='containment', model_provider='ollama', model_name='qwen2.5:0.5b', instructions='Execute containment actions: isolate hosts, disable accounts.'),
        AgentConfig(agent_id='investigate-001', role='investigation', model_provider='ollama', model_name='qwen2.5:0.5b', instructions='Deep forensic analysis and IoC extraction.'),
        AgentConfig(agent_id='compliance-001', role='compliance', model_provider='ollama', model_name='qwen2.5:0.5b', instructions='Regulatory checks and audit trail verification.'),
        AgentConfig(agent_id='report-001', role='reporting', model_provider='ollama', model_name='qwen2.5:0.5b', instructions='Generate incident summaries and stakeholder briefs.'),
    ]
    for cfg in agents:
        agent = await agent_registry.register(cfg)
        print(f'  Registered: {agent.agent_id} ({agent.role})')
    print(f'  Total agents: {len(agent_registry.list_all())}')

asyncio.run(register_agents())
"
echo ""

# ── 2. Instantiate Dictator ──────────────────────────────
echo ">>> Instantiating Dictator agent..."
python3 -c "
from magenta.agents.dictator import DictatorAgent
dictator = DictatorAgent()
print(f'  Dictator: {dictator.config.agent_id} (role: {dictator.config.role})')
print(f'  Status: {dictator.status}')
"
echo ""

# ── 3. Verify agent registry ─────────────────────────────
echo ">>> Verifying agent registry..."
python3 -c "
import asyncio
from magenta.core.agent import agent_registry

async def verify():
    agents = agent_registry.list_all()
    print(f'  Registry contains {len(agents)} agents:')
    for a in agents:
        print(f'    - {a.agent_id} ({a.role}) on {a.config.model_provider}/{a.config.model_name}')

asyncio.run(verify())
"
echo ""

# ── 4. Create sample mission ──────────────────────────────
echo ">>> Creating sample mission..."
python3 -c "
import asyncio
from magenta.core.mission import mission_manager
from magenta.core.models import Mission, MissionStatus

async def create_sample():
    mission = Mission(
        mission_id='mission-sample-001',
        title='Sample phishing triage mission',
        description='Auto-created during state initialization for pipeline testing.',
        status=MissionStatus.created,
        alert_source='manual',
        alert_id='sample-alert-001',
    )
    await mission_manager.create_mission(mission)
    print(f'  Mission: {mission.mission_id} ({mission.status.value})')

asyncio.run(create_sample())
"
echo ""

# ── 5. Final status ──────────────────────────────────────
echo "=== Initialization Complete ==="
echo "Services: Redis, OLLAMA, Open WebUI, Pipelines, OTel Collector, MCPO"
echo "Agents:   6 base agents + Dictator registered"
echo "Mission:  1 sample mission created"
echo ""
echo "Next steps:"
echo "  - Open http://localhost:3000 (Open WebUI)"
echo "  - Type: dictator_status (verify pipeline tools work)"
echo "  - Type: check_pending_approvals (verify approval gate)"
