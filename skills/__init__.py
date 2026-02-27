"""HydroOS Skills — L3 fixed workflow orchestration.
HydroOS 技能层 — L3 固定工作流编排。

Skills are immutable, verified workflows that chain MCP Tools
in predetermined sequences. Agents select which Skill to invoke.
"""

from skills.base_skill import BaseSkill, SkillMetadata, SkillResult, discover_skills
from skills.control_system_design import ControlSystemDesignSkill
from skills.daily_report import DailyReportSkill
from skills.data_analysis_predict import DataAnalysisPredictSkill
from skills.evap_optimization import EvapOptimizationSkill
from skills.forecast_skill import ForecastSkill
from skills.four_prediction_loop import FourPredictionLoopSkill
from skills.full_lifecycle import FullLifecycleSkill
from skills.global_dispatch import GlobalDispatchSkill
from skills.leak_diagnosis import LeakDiagnosisSkill
from skills.odd_assessment import ODDAssessmentSkill
from skills.optimization_design import OptimizationDesignSkill
from skills.plan_skill import PlanSkill
from skills.rehearsal_skill import RehearsalSkill
from skills.reuse_scheduling import ReuseSchedulingSkill
from skills.warning_skill import WarningSkill

__all__ = [
    "BaseSkill",
    "SkillResult",
    "SkillMetadata",
    "discover_skills",
    "ForecastSkill",
    "WarningSkill",
    "RehearsalSkill",
    "PlanSkill",
    "FourPredictionLoopSkill",
    "DataAnalysisPredictSkill",
    "ODDAssessmentSkill",
    "ControlSystemDesignSkill",
    "OptimizationDesignSkill",
    "FullLifecycleSkill",
    "LeakDiagnosisSkill",
    "EvapOptimizationSkill",
    "ReuseSchedulingSkill",
    "GlobalDispatchSkill",
    "DailyReportSkill",
]
