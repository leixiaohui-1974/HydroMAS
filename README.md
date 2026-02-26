# HydroOS-Agent

Multi-Agent Intelligent Decision Platform for Water Network Lifecycle Management.

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

## MVP Target

Single-tank system demonstrating the full pipeline:
Simulation → Identification → Prediction → Control → ODD Assessment → Evaluation
