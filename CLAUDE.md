# HydroOS-Agent — Multi-Agent Intelligent Decision Platform

Water network lifecycle management platform based on a five-layer architecture.
水网全生命周期管理的多智能体智能决策平台。

Extended for **alumina plant water network intelligence** (氧化铝厂水网智能化):
- Daily intake 10,400 m³ (Wujiang River 7,800 + Flood Channel 2,600)
- 12+ workshop nodes, evaporation loss ~4,200 m³/d
- Target: 15-20% water saving, reuse rate 36%→50%+, pump energy -8-12%

Includes **OpenClaw content pipeline** for multi-agent content production:
- Writing → Illustration → Publishing (Feishu/WeChat) → Video → PPT
- Multi-agent: ContentPlanner → ContentReviewer → ContentPublisher → ContentOrchestrator

## Architecture (五层架构)

```
L4  Agents      — 15 Agents (all extend BaseAgent with unified lifecycle)
                   Domain:  Orchestrator, Planning, Analysis, Report, Safety, Handuo LLM, RL Dispatch (7)
                   DevOps:  DevPlanner, DevReviewer, DevTester, DevOrchestrator (4)
                   Content: ContentPlanner, ContentReviewer, ContentPublisher, ContentOrchestrator (4)
                   Infrastructure: BaseAgent, AgentMessage, MessageBus, AgentRegistry,
                                   AgentContext, MultiAgentExecutor, AgentHealthMonitor,
                                   CapabilityNegotiator, SpanRecorder, CircuitBreakerRegistry,
                                   AgentRateLimiterRegistry, IntentClassifier,
                                   AdaptiveScheduler
L3  Skills      — 17 Skills (四预 + leak diagnosis + evap optimization + reuse + dispatch
                             + daily report + collaborative_dev + content_pipeline)
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
├── skills/               # L3: Fixed workflows (17 skills)
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
│   ├── leak_diagnosis.py      # Balance→Anomaly→GNN→Localize→Acoustic
│   ├── evap_optimization.py   # Tower→Calcination→RedMud→Total→Suggest
│   ├── reuse_scheduling.py    # Match→Optimize→Evaluate
│   ├── global_dispatch.py     # Demand→Evap→Dispatch→ODD
│   ├── daily_report.py        # Balance→Anomaly→KPI→Evap→Report
│   └── collaborative_dev.py   # Multi-agent dev: Plan→Review→Test→Integrate
├── agents/               # L4: Multi-agent orchestration (Domain + DevOps)
│   ├── base_agent.py    #   BaseAgent ABC, AgentCard, AgentStatus (NEW)
│   ├── message.py       #   AgentMessage, MessageType, MessageBus (NEW)
│   ├── registry.py      #   AgentRegistry — discovery by capability/type (NEW)
│   ├── context.py       #   AgentContext — shared blackboard + trace (NEW)
│   ├── executor.py      #   MultiAgentExecutor — DAG-based execution (NEW)
│   ├── orchestrator.py   #   Main entry point, 4-level routing, collaborative workflow
│   ├── planning_agent.py #   Task decomposition, DAG planning
│   ├── analysis_agent.py #   Flexible data analysis + water balance/evap/reuse analysis
│   ├── report_agent.py   #   Markdown reports + water balance/daily/leak reports
│   ├── safety_agent.py   #   ODD guardian + alumina 12-dim ODD + pressure/quality checks
│   ├── handuo_agent.py   #   瀚铎水网大模型 — RAG-based domain Q&A
│   ├── rl_dispatch_agent.py # RL dispatch — PPO/rule-based water scheduling
│   ├── dev_planner.py    #   Requirement analysis → DAG plan generation
│   ├── dev_reviewer.py   #   Multi-dimension code review (style, logic, security, perf)
│   ├── dev_tester.py     #   Test generation + quality gate
│   ├── dev_orchestrator.py #  Analyse→Plan→Implement→Review→Test pipeline
│   └── agent_cards/      #   Agent capability definitions (11 cards)
├── openclaw/             # OpenClaw content pipeline (multi-agent) + gateway client
│   ├── hydromas_client.py #  Stdlib-only Python SDK for OpenClaw→HydroMAS (NEW)
│   ├── models.py         #   ContentStage, ArticleConfig, ImageConfig, PublishConfig, VideoConfig, ContentPipeline
│   ├── agents/           #   Content agents
│   │   ├── content_planner.py      # Requirement analysis → content plan
│   │   ├── content_reviewer.py     # Multi-dimension review (structure, style, technical, compliance)
│   │   ├── content_publisher.py    # Multi-channel publish (Feishu, WeChat, video, PPT)
│   │   ├── content_orchestrator.py # Full pipeline orchestration
│   │   └── agent_cards/            # 3 agent cards (JSON)
│   └── skills/
│       └── content_pipeline_skill.py # HydroMAS BaseSkill wrapper
├── openclaw-content-pipeline/  # Original OpenClaw skill scripts + articles
│   ├── skills/           #   Feishu image pipeline, WeChat publish, article-to-video, hydromas-assistant
│   ├── articles/         #   Markdown article drafts
│   └── configs/          #   Pipeline & video JSON configs
├── integrations/         # External platform integrations
│   ├── feishu_bot.py     #   Bot webhook handler (message routing, command dispatch)
│   ├── feishu_alert.py   #   Alert sender (card messages, batch alerts, ODD alerts)
│   └── feishu_sync.py    #   Bitable sync (read/write/upsert, schema management)
├── knowledge/            # Knowledge management
│   ├── process_ontology.py #  Alumina process ontology loader
│   └── rag_service.py     #  TF-IDF based RAG retrieval service
├── web/                  # FastAPI web platform
│   ├── app.py            #   FastAPI app with 20 routers
│   ├── deps.py           #   Singletons: orchestrator, registry, bus, executor, feishu, etc.
│   ├── models.py         #   Pydantic models (original + 10 new)
│   ├── routers/          #   API endpoints (20 routers, ~90 endpoints)
│   │   ├── gateway.py    #   OpenClaw unified gateway: chat/skill/roles/skills/health (NEW)
│   │   └── feishu.py     #   Feishu webhook/alert/sync/status endpoints (NEW)
│   ├── static/           #   Frontend assets
│   └── templates/        #   Jinja2 templates
├── data/                 # Configuration files
│   ├── tank_config.json       #   Default tank/control/simulation params
│   ├── odd_specs.json         #   6-dimension ODD specification
│   ├── alumina_config.json    #   Alumina plant node/edge/evap config
│   ├── alumina_odd_specs.json #   12-dimension alumina ODD
│   ├── process_ontology.json  #   Process entities and fault modes
│   └── sample_timeseries.csv
├── tests/                # pytest test suite (1725 tests)
│   ├── test_core/        #   Core module unit tests
│   ├── test_compute/     #   Ray compute tests
│   ├── test_mcp_servers/ #   MCP server tests
│   ├── test_skills/      #   Skill workflow tests
│   ├── test_agents/      #   Agent tests (domain + dev pipeline + multi-agent infra)
│   ├── test_web/         #   Web API tests (all 20 routers with dedicated test files)
│   ├── test_scenarios/   #   E2E scenario tests (6 scenarios: R1/D1/O1 tank + R2/D2/O2 alumina)
│   ├── test_integrations/ #  Feishu integration tests (unit + E2E)
│   └── test_openclaw/    #   OpenClaw content pipeline tests
├── Dockerfile            # Production container
├── docker-compose.yml    # Full stack with TDengine + Neo4j
├── .dockerignore         # Exclude tests/docs from Docker image
├── .env.example          # Environment variable template
├── deploy.sh             # Deployment script (dev/prod/test/docker)
└── pyproject.toml
```

## Key Concepts

- **Tool → Skill → Agent hierarchy**: Tools are atomic, Skills are fixed workflows, Agents are flexible
- **四预 System**: 预报→预警→预演→预案 (Forecast→Warning→Rehearsal→Plan)
- **ODD**: 6-dimensional (tank) / 12-dimensional (alumina plant) safety boundary with 3-zone classification (normal/extended/mrc)
- **WNAL**: Water Network Autonomy Level (L0-L5)
- **Tank model**: `dh/dt = (Q_in - Q_out) / A`, `Q_out = Cd * a * sqrt(2*g*h)`
- **Water balance**: `R = Q_in - Q_out - Q_loss - Q_evap - dV/dt` (residual ≈ 0 when balanced)
- **Merkel evaporation**: `E = Q × Cp × ΔT / L_v × K_evap`
- **Leak detection**: Graph Autoencoder (GAT) + acoustic fusion for pipe segment localization
- **Multi-agent infrastructure**: BaseAgent → AgentMessage/MessageBus → AgentRegistry → AgentContext → MultiAgentExecutor → AgentHealthMonitor
- **Skill→Agent bridge**: BaseSkill.call_agent() connects L3 Skills to L4 Agents via MessageBus
- **Multi-agent DevOps**: DevPlanner (requirement→DAG) → DevReviewer (code review) → DevTester (test gen) → DevOrchestrator (pipeline)
- **Content pipeline**: ContentPlanner → ContentReviewer → ContentPublisher → ContentOrchestrator (writing→review→publish)
- **Scenario testing**: Research (写作+建模+管理=科研), Design (MBD设计), Operations (运维) × Tank/Alumina = 6 scenarios
- **Feishu integration**: Bot handler (webhook → /api/feishu/webhook), Alert sender (card messages), Bitable sync (CRUD), singleton orchestrator injection
- **OpenClaw gateway**: Unified `/api/gateway/` entry point — chat (NL), skill (direct), roles, skills listing, health; three roles: researcher/designer/operator
- **HydroMASClient**: Stdlib-only Python SDK (`openclaw/hydromas_client.py`) for OpenClaw skill integration — no external deps

## Import Examples

```python
# Core imports
from core.simulation import TankParams, run_simulation
from core.control import PIDController, MPCController, PIDParams
from core.evaluation import evaluate_performance, assess_wnal
from core.prediction import predict_linear
from core.odd import check_odd

# Alumina extension imports
from core.simulation import NetworkParams, DigitalTwinEngine, TwinState
from core.water_balance import BalanceNode, calc_node_residual, build_balance_graph, calc_full_balance
from core.evaporation import CoolingTowerParams, calc_evaporation_merkel, calc_red_mud_water
from core.process_coupling import ProcessState, calc_total_process_demand
from core.detection import network_to_dict_graph, detect_leak, AcousticEvent

# Domain skills
from skills import LeakDiagnosisSkill, EvapOptimizationSkill, GlobalDispatchSkill
from skills import ReuseSchedulingSkill, DailyReportSkill
from skills.collaborative_dev import CollaborativeDevSkill

# Multi-agent infrastructure
from agents import BaseAgent, AgentCard, AgentStatus
from agents import AgentMessage, MessageType, MessageBus
from agents import AgentRegistry, AgentContext
from agents import MultiAgentExecutor, ExecutionPlan, ExecutionTask

# Domain agents
from agents import OrchestratorAgent, HanduoAgent, RLDispatchAgent
from agents.safety_agent import SafetyAgent

# DevOps agents (multi-agent collaborative development)
from agents.dev_planner import DevPlannerAgent, RequirementSpec
from agents.dev_reviewer import DevReviewerAgent
from agents.dev_tester import DevTesterAgent
from agents.dev_orchestrator import DevOrchestratorAgent

# OpenClaw content pipeline agents
from openclaw.agents.content_planner import ContentPlannerAgent
from openclaw.agents.content_reviewer import ContentReviewerAgent
from openclaw.agents.content_publisher import ContentPublisherAgent
from openclaw.agents.content_orchestrator import ContentOrchestratorAgent
from openclaw.skills.content_pipeline_skill import ContentPipelineSkill

# Integrations
from integrations.feishu_bot import FeishuBotHandler
from integrations.feishu_alert import FeishuAlertSender
from integrations.feishu_sync import FeishuBitableSync

# OpenClaw gateway client (stdlib only, for skill integration)
from openclaw.hydromas_client import HydroMASClient

# Knowledge
from knowledge import load_ontology, query_ontology, RAGService
```

## Running Tests

```bash
pytest                          # All 1725 tests
pytest tests/test_core/         # Core module tests only
pytest tests/test_skills/       # Skill workflow tests
pytest tests/test_agents/       # Agent tests (domain + dev pipeline + multi-agent infra)
pytest tests/test_web/          # Web API tests
pytest tests/test_scenarios/    # E2E scenario tests (R1/D1/O1 + R2/D2/O2)
pytest tests/test_integrations/ # Feishu integration tests
pytest tests/test_openclaw/     # OpenClaw content pipeline tests
pytest -x                       # Stop on first failure
pytest -q                       # Quiet output
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
