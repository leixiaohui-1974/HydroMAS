# HydroMAS

Multi-Agent intelligent decision platform for water network lifecycle management.

## Architecture

Five-layer architecture (L0-L4):

- **L0 Data & Perception**: Sensor data, time-series storage, configuration
- **L1 Distributed Compute**: Ray-based scalable runtime
- **L2 MCP Tool Layer**: Atomic computation modules exposed via MCP
- **L3 Skill Layer**: Fixed workflow orchestration
- **L4 Cognitive Layer**: LangGraph-based multi-agent system

## Quick Start

```bash
pip install -e ".[dev]"
pytest
```

Install metadata now publishes the package as `hydromas`. Legacy
`hydroclaw` imports remain available as a compatibility surface during the
ongoing migration.

## MVP Target

Single-tank system demonstrating the full pipeline:
Simulation → Identification → Prediction → Control → ODD Assessment → Evaluation
