# Magenta Framework — Context Engineering

This directory contains the context engineering reference for the **Magenta Framework**: the multi-agent teaming layer that powers the Agentic Security Telemetry Fabric.

## Purpose

The Magenta Framework defines how AI agents team up like cybersecurity professionals — with specialization, delegation, escalation, consensus, and human oversight. This context layer ensures that every agent operating within the framework understands its role, the teaming structure, and the architectural boundaries.

## Files

| File | Content |
|---|---|
| `/architecture/frameworks/magenta.md` | Complete framework specification: agents, missions, swarms, LLM abstraction, teaming structures |
| `multiagentarchitecture-ref.md` | Deep dive into agent communication patterns, delegation protocols, memory architecture, and tool integration |
| `agentic-teaming-methodologies.md` | Five teaming structures (Supervisor, Debate, Pipeline, Mesh, Referee) with detailed protocols |

## Key Principles

1. **LLM-agnostic** — Agents run on OLLAMA, free APIs, or enterprise models interchangeably
2. **Dynamic swarms** — Teams assemble per-mission, not per-playbook
3. **Immutable audit** — Every agent reasoning step is logged for replay and compliance
4. **Human-in-the-loop by design** — Risk-graded escalation tiers keep humans in control
5. **Open-weight first** — No dependency on proprietary models; all patterns work with local open models

## Quick Links

- [Magenta Framework (full spec)](../../architecture/frameworks/magenta.md)
- [Multi-Agent Architecture Reference](./multiagentarchitecture-ref.md)
- [Agentic Teaming Methodologies](./agentic-teaming-methodologies.md)
- [DTP Pipeline Reference](../../architecture/readme.md)
