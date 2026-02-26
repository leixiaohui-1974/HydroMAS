# HydroOS-Agent — Multi-Agent Intelligent Decision Platform

Water network lifecycle management platform based on a five-layer architecture.
水网全生命周期管理的多智能体智能决策平台。

## Architecture (五层架构)

```
L4  Agents      — Flexible decision makers (Orchestrator, Planning, Analysis, Report, Safety)
L3  Skills      — Immutable verified workflows (10 skills including 四预)
L2  MCP Servers — Tool endpoints via FastMCP (9 domain servers)
L1  Compute     — Ray-based distributed computation
L0  Core        — Domain algorithms (simulation, control, prediction, etc.)
```

## Quick Start

```bash
pip install -e ".[dev]"
pytest                    # Run all tests
```

## Project Structure

```
HydroMAS/
├── core/                 # L0: Domain computation
│   ├── simulation/       #   Tank ODE model, Euler/RK4 solvers
│   ├── control/          #   PID and MPC controllers
│   ├── prediction/       #   Linear/polynomial forecasting
│   ├── scheduling/       #   LP-based inflow optimization
│   ├── design/           #   Tank sizing, sensitivity analysis
│   ├── evaluation/       #   Performance metrics, WNAL assessment
│   ├── data_clean/       #   Outlier detection, interpolation
│   ├── odd/              #   Operational Design Domain monitoring
│   ├── identification/   #   ARX model, least-squares parameter ID
│   └── config.py         #   Config loader for data/*.json
├── compute/              # L1: Ray distributed computing
│   ├── ray_config.py     #   Ray initialization
│   ├── distributed_sim.py #  Parallel simulation
│   ├── distributed_optim.py # Parallel optimization
│   ├── parallel_data.py  #   Parallel data cleaning
│   └── actor_controller.py #  Ray Actor MPC
├── mcp_servers/          # L2: FastMCP tool endpoints
│   ├── simulation_server.py
│   ├── control_server.py
│   ├── prediction_server.py
│   ├── scheduling_server.py
│   ├── dataclean_server.py
│   ├── evaluation_server.py
│   ├── odd_server.py
│   ├── design_server.py
│   └── identification_server.py
├── skills/               # L3: Fixed workflows
│   ├── base_skill.py     #   BaseSkill ABC, SkillResult, discovery
│   ├── forecast_skill.py #   预报 Forecast
│   ├── warning_skill.py  #   预警 Warning
│   ├── rehearsal_skill.py #  预演 Rehearsal
│   ├── plan_skill.py     #   预案 Plan
│   ├── four_prediction_loop.py # 四预闭环
│   ├── full_lifecycle.py #   Full lifecycle
│   ├── control_system_design.py
│   ├── data_analysis_predict.py
│   ├── odd_assessment.py
│   └── optimization_design.py
├── agents/               # L4: Multi-agent orchestration
│   ├── orchestrator.py   #   Main entry point, intent routing
│   ├── planning_agent.py #   Task decomposition, DAG planning
│   ├── analysis_agent.py #   Flexible data analysis
│   ├── report_agent.py   #   Markdown report generation
│   └── safety_agent.py   #   ODD guardian, MRC triggering
├── data/                 # Configuration files
│   ├── tank_config.json  #   Default tank/control/simulation params
│   ├── odd_specs.json    #   6-dimension ODD specification
│   └── sample_timeseries.csv
├── tests/                # pytest test suite
└── pyproject.toml
```

## Key Concepts

- **Tool → Skill → Agent hierarchy**: Tools are atomic, Skills are fixed workflows, Agents are flexible
- **四预 System**: 预报→预警→预演→预案 (Forecast→Warning→Rehearsal→Plan)
- **ODD**: 6-dimensional safety boundary with 3-zone classification (normal/extended/MRC)
- **WNAL**: Water Network Autonomy Level (L0-L5)
- **Tank model**: `dh/dt = (Q_in - Q_out) / A`, `Q_out = Cd * a * sqrt(2*g*h)`

## Import Examples

```python
# Direct subpackage imports
from core.simulation import TankParams, run_simulation
from core.control import PIDController, MPCController
from core.evaluation import evaluate_performance, assess_wnal

# Config loading
from core import load_tank_config, get_default_tank_params

# Skills and Agents
from skills import ForecastSkill, FourPredictionLoopSkill
from agents import OrchestratorAgent
```

## Running Tests

```bash
pytest                      # All tests
pytest tests/test_core/     # Core module tests only
pytest -x                   # Stop on first failure
pytest -q                   # Quiet output
```

## Configuration

Default parameters are in `data/tank_config.json` and can be loaded via:
```python
from core.config import load_tank_config, get_default_tank_params
config = load_tank_config()
tank_params = get_default_tank_params()  # {"area": 1.0, "cd": 0.6, ...}
```

## Tech Stack

- Python 3.11+, NumPy, SciPy, PuLP
- Ray for distributed computing
- FastMCP for tool protocol
- pytest + pytest-asyncio for testing
