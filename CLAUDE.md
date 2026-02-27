# HydroOS-Agent — Multi-Agent Intelligent Decision Platform

Water network lifecycle management platform based on a five-layer architecture.
水网全生命周期管理的多智能体智能决策平台。

Extended for **alumina plant water network intelligence** (氧化铝厂水网智能化):
- Daily intake 10,400 m³ (Wujiang River 7,800 + Flood Channel 2,600)
- 12+ workshop nodes, evaporation loss ~4,200 m³/d
- Target: 15-20% water saving, reuse rate 36%→50%+, pump energy -8-12%

## Architecture (五层架构)

```
L4  Agents      — 7 Agents (Orchestrator, Planning, Analysis, Report, Safety, Handuo LLM, RL Dispatch)
L3  Skills      — 15 Skills (四预 + leak diagnosis + evap optimization + reuse + dispatch + daily report)
L2  MCP Servers — 13 FastMCP servers (9 original + water_balance + evaporation + leak_detection + reuse)
L1  Compute     — Ray-based distributed computation
L0  Core        — 14 domain algorithm submodules
```

## Quick Start

```bash
pip install -e ".[dev]"
pytest                    # Run all tests

# Optional dependencies
pip install -e ".[alumina]"   # WNTR + NetworkX for network simulation
pip install -e ".[gnn]"       # torch + torch_geometric for GNN leak detection
pip install -e ".[web]"       # FastAPI web platform
```

## Project Structure

```
HydroMAS/
├── core/                 # L0: Domain computation
│   ├── simulation/       #   Tank ODE + WNTR network model + Digital Twin
│   ├── control/          #   PID and MPC controllers
│   ├── prediction/       #   Linear/polynomial forecasting
│   ├── scheduling/       #   LP-based inflow optimization
│   ├── design/           #   Tank sizing, sensitivity analysis
│   ├── evaluation/       #   Performance metrics, WNAL assessment
│   ├── data_clean/       #   Outlier detection, interpolation
│   ├── odd/              #   Operational Design Domain monitoring
│   ├── identification/   #   ARX model, least-squares parameter ID
│   ├── water_balance/    #   Plant-wide water balance accounting (NEW)
│   ├── evaporation/      #   Merkel cooling tower + calcination + red mud (NEW)
│   ├── process_coupling/ #   Alumina process water demand calculation (NEW)
│   ├── detection/        #   GNN leak detection + acoustic fusion (NEW)
│   └── config.py         #   Config loader for data/*.json
├── compute/              # L1: Ray distributed computing
│   ├── ray_config.py     #   Ray initialization
│   ├── distributed_sim.py #  Parallel simulation
│   ├── distributed_optim.py # Parallel optimization
│   ├── parallel_data.py  #   Parallel data cleaning
│   └── actor_controller.py #  Ray Actor MPC
├── mcp_servers/          # L2: FastMCP tool endpoints
│   ├── simulation_server.py    #  simulate_tank + simulate_network (NEW)
│   ├── control_server.py
│   ├── prediction_server.py    #  predict_future + predict_demand + predict_evap_hybrid (NEW)
│   ├── scheduling_server.py    #  optimize_schedule + optimize_global_dispatch (NEW)
│   ├── dataclean_server.py
│   ├── evaluation_server.py    #  evaluate_performance + evaluate_water_kpi (NEW)
│   ├── odd_server.py           #  check_odd + check_alumina_odd (NEW)
│   ├── design_server.py
│   ├── identification_server.py
│   ├── water_balance_server.py  # (NEW) Node balance, full plant, anomaly detection
│   ├── evaporation_server.py    # (NEW) Merkel, calcination, red mud, total loss
│   ├── leak_detection_server.py # (NEW) Graph builder, GNN detect, localize, acoustic fusion
│   └── reuse_server.py          # (NEW) Quality matching, LP scheduling, benefit evaluation
├── skills/               # L3: Fixed workflows
│   ├── base_skill.py     #   BaseSkill ABC, SkillResult, discovery, 35 tool mappings
│   ├── forecast_skill.py #   预报 Forecast
│   ├── warning_skill.py  #   预警 Warning
│   ├── rehearsal_skill.py #  预演 Rehearsal
│   ├── plan_skill.py     #   预案 Plan
│   ├── four_prediction_loop.py # 四预闭环
│   ├── full_lifecycle.py #   Full lifecycle
│   ├── control_system_design.py
│   ├── data_analysis_predict.py
│   ├── odd_assessment.py
│   ├── optimization_design.py
│   ├── leak_diagnosis.py      # (NEW) Balance→Anomaly→GNN→Localize→Acoustic
│   ├── evap_optimization.py   # (NEW) Tower→Calcination→RedMud→Total→Suggest
│   ├── reuse_scheduling.py    # (NEW) Match→Optimize→Evaluate
│   ├── global_dispatch.py     # (NEW) Demand→Evap→Dispatch→ODD
│   └── daily_report.py        # (NEW) Balance→Anomaly→KPI→Evap→Report
├── agents/               # L4: Multi-agent orchestration
│   ├── orchestrator.py   #   Main entry point, 20 tool keywords, 15 skills
│   ├── planning_agent.py #   Task decomposition, DAG planning
│   ├── analysis_agent.py #   Flexible data analysis + water balance/evap/reuse analysis (NEW)
│   ├── report_agent.py   #   Markdown reports + water balance/daily/leak reports (NEW)
│   ├── safety_agent.py   #   ODD guardian + alumina 12-dim ODD + pressure/quality checks (NEW)
│   ├── handuo_agent.py   #   (NEW) 瀚铎水网大模型 — RAG-based domain Q&A
│   ├── rl_dispatch_agent.py # (NEW) RL dispatch — PPO/rule-based water scheduling
│   └── agent_cards/      #   Agent capability definitions (7 cards)
├── knowledge/            # Knowledge management (NEW)
│   ├── process_ontology.py #  Alumina process ontology loader
│   └── rag_service.py     #  TF-IDF based RAG retrieval service
├── web/                  # FastAPI web platform
│   ├── app.py            #   FastAPI app with 17 routers
│   ├── models.py         #   Pydantic models (original + 6 new)
│   ├── routers/          #   API endpoints (11 original + 6 new)
│   ├── static/           #   Frontend assets
│   └── templates/        #   Jinja2 templates
├── data/                 # Configuration files
│   ├── tank_config.json       #   Default tank/control/simulation params
│   ├── odd_specs.json         #   6-dimension ODD specification
│   ├── alumina_config.json    #   (NEW) Alumina plant node/edge/evap config
│   ├── alumina_odd_specs.json #   (NEW) 12-dimension alumina ODD
│   ├── process_ontology.json  #   (NEW) Process entities and fault modes
│   └── sample_timeseries.csv
├── tests/                # pytest test suite (900+ tests)
├── Dockerfile            # (NEW) Production container
├── docker-compose.yml    # (NEW) Full stack with TDengine + Neo4j
└── pyproject.toml
```

## Key Concepts

- **Tool → Skill → Agent hierarchy**: Tools are atomic, Skills are fixed workflows, Agents are flexible
- **四预 System**: 预报→预警→预演→预案 (Forecast→Warning→Rehearsal→Plan)
- **ODD**: 6-dimensional (tank) / 12-dimensional (alumina plant) safety boundary with 3-zone classification
- **WNAL**: Water Network Autonomy Level (L0-L5)
- **Tank model**: `dh/dt = (Q_in - Q_out) / A`, `Q_out = Cd * a * sqrt(2*g*h)`
- **Water balance**: `R = Q_in - Q_out - Q_loss - Q_evap - dV/dt` (residual ≈ 0 when balanced)
- **Merkel evaporation**: `E = Q × Cp × ΔT / L_v × K_evap`
- **Leak detection**: Graph Autoencoder (GAT) + acoustic fusion for pipe segment localization

## Import Examples

```python
# Original core imports
from core.simulation import TankParams, run_simulation
from core.control import PIDController, MPCController
from core.evaluation import evaluate_performance, assess_wnal

# New alumina extension imports
from core.simulation import NetworkParams, DigitalTwinEngine, TwinState
from core.water_balance import BalanceNode, calc_node_residual, build_balance_graph, calc_full_balance
from core.evaporation import CoolingTowerParams, calc_evaporation_merkel, calc_red_mud_water
from core.process_coupling import ProcessState, calc_total_process_demand
from core.detection import network_to_dict_graph, detect_leak, AcousticEvent

# New skills
from skills import LeakDiagnosisSkill, EvapOptimizationSkill, GlobalDispatchSkill
from skills import ReuseSchedulingSkill, DailyReportSkill

# New agents
from agents import OrchestratorAgent, HanduoAgent, RLDispatchAgent

# Knowledge
from knowledge import load_ontology, query_ontology, RAGService
```

## Running Tests

```bash
pytest                      # All tests
pytest tests/test_core/     # Core module tests only
pytest tests/test_skills/   # Skill tests
pytest tests/test_agents/   # Agent tests
pytest tests/test_web/      # Web API tests
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

Alumina plant config:
```python
import json
with open("data/alumina_config.json") as f:
    alumina_config = json.load(f)
# alumina_config["daily_intake_m3"] == 10400
```

## Tech Stack

- Python 3.11+, NumPy, SciPy, PuLP
- Ray for distributed computing
- FastMCP for tool protocol
- FastAPI + Jinja2 for web platform
- WNTR (optional) for EPANET network simulation
- torch + torch_geometric (optional) for GNN leak detection
- pytest + pytest-asyncio for testing
- Docker + TDengine + Neo4j for production deployment
