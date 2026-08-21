# ADR 0003: Module Classification & Strict Inward Import Boundaries

## Status
Accepted

## Context
Accidental coupling allowed heavy research dependencies (e.g., LangGraph, SciPy, NetworkX) to be imported during default server startup, slowing initialization and increasing memory footprint on constrained devices.

## Decision
We establish five architectural tiers:
- **Core**: Minimalist 5-tool server, Pydantic, SQLite.
- **Optional**: Separately installed adapters (`[web]`, `[vectors]`).
- **Experimental**: Research graphs excluded from default runtime.
- **Legacy**: Compatibility-only layer receiving security fixes only.
- **Remove**: Deprecated placeholders.

Import rules: `api -> contracts -> verification -> memory -> persistence`. Core runtime must never import experimental graphs.

## Consequences
- Startup latency $<1.5	ext{s}$, memory $<35	ext{MB}$ RSS.
