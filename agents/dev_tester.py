"""Development Tester Agent — test generation and execution.
开发测试 Agent — 测试生成与执行。

Generates test cases, validates test coverage, and orchestrates
test execution for the HydroMAS development pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from agents.base_agent import BaseAgent
from agents.message import AgentMessage, MessageType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DevTestCase:
    """A single test case. / 单个测试用例。"""

    id: str
    name: str
    description: str
    category: str = "unit"  # unit, integration, e2e, regression, safety
    target_module: str = ""
    target_function: str = ""
    inputs: dict = field(default_factory=dict)
    expected: dict = field(default_factory=dict)
    assertions: list[str] = field(default_factory=list)
    priority: str = "medium"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "target_module": self.target_module,
            "target_function": self.target_function,
            "inputs": self.inputs,
            "expected": self.expected,
            "assertions": self.assertions,
            "priority": self.priority,
        }


@dataclass
class DevTestSuite:
    """A collection of test cases. / 测试用例集。"""

    name: str
    test_cases: list[DevTestCase] = field(default_factory=list)
    category: str = "unit"
    created_at: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    def add_case(self, case: DevTestCase) -> None:
        self.test_cases.append(case)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "created_at": self.created_at,
            "test_count": len(self.test_cases),
            "test_cases": [tc.to_dict() for tc in self.test_cases],
        }


@dataclass
class DevTestReport:
    """Test execution report. / 测试执行报告。"""

    suite_name: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[dict] = field(default_factory=list)
    duration_seconds: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    @property
    def pass_rate(self) -> float:
        return self.passed / max(self.total, 1)

    @property
    def all_passed(self) -> bool:
        return self.failed == 0 and self.total > 0

    def to_dict(self) -> dict:
        return {
            "suite_name": self.suite_name,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "pass_rate": round(self.pass_rate, 4),
            "all_passed": self.all_passed,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Test generation templates by module
# ---------------------------------------------------------------------------

MODULE_TEST_TEMPLATES: dict[str, list[dict]] = {
    "simulation": [
        {
            "name": "test_{func}_basic_output",
            "description": "Verify basic output structure and types",
            "assertions": [
                "result is not None",
                "isinstance(result, dict)",
                "all required keys present",
            ],
        },
        {
            "name": "test_{func}_physical_constraints",
            "description": "Verify physical constraints (non-negative, bounded)",
            "assertions": [
                "water level >= 0",
                "flow rate >= 0",
                "pressure within bounds",
            ],
        },
        {
            "name": "test_{func}_edge_cases",
            "description": "Test edge cases (zero input, max capacity)",
            "assertions": [
                "handles zero input gracefully",
                "handles max capacity without overflow",
            ],
        },
    ],
    "control": [
        {
            "name": "test_{func}_setpoint_tracking",
            "description": "Controller tracks setpoint within tolerance",
            "assertions": [
                "steady-state error < tolerance",
                "output within actuator limits",
            ],
        },
        {
            "name": "test_{func}_disturbance_rejection",
            "description": "Controller rejects step disturbance",
            "assertions": [
                "recovers to setpoint after disturbance",
                "no sustained oscillation",
            ],
        },
    ],
    "water_balance": [
        {
            "name": "test_{func}_mass_conservation",
            "description": "Verify mass conservation (residual near zero)",
            "assertions": [
                "abs(residual) < threshold",
                "Q_in = Q_out + Q_loss + Q_evap + dV/dt + residual",
            ],
        },
        {
            "name": "test_{func}_anomaly_detection",
            "description": "Detect injected anomaly correctly",
            "assertions": [
                "anomaly flagged when residual > threshold",
                "no false positive in normal data",
            ],
        },
    ],
    "evaporation": [
        {
            "name": "test_{func}_merkel_physics",
            "description": "Merkel evaporation within physical bounds",
            "assertions": [
                "evaporation_rate > 0",
                "evaporation_rate < water_flow (not all water evaporates)",
                "increases with temperature difference",
            ],
        },
    ],
    "detection": [
        {
            "name": "test_{func}_no_leak_baseline",
            "description": "No false alarm on clean data",
            "assertions": [
                "leak_detected is False for normal data",
            ],
        },
        {
            "name": "test_{func}_leak_injection",
            "description": "Detect injected leak correctly",
            "assertions": [
                "leak_detected is True when leak present",
                "localization near injection point",
            ],
        },
    ],
    "odd": [
        {
            "name": "test_{func}_green_zone",
            "description": "Normal state classified as green zone",
            "assertions": [
                "zone == 'green' for normal parameters",
            ],
        },
        {
            "name": "test_{func}_red_zone",
            "description": "Extreme state classified as red zone",
            "assertions": [
                "zone == 'red' for extreme parameters",
                "MRC actions recommended",
            ],
        },
    ],
}

# Scenario-based test templates (科研/设计/运维)
SCENARIO_TEST_TEMPLATES: dict[str, list[dict]] = {
    "research": [
        {
            "name": "test_experiment_reproducibility",
            "description": "Same inputs produce same outputs (科研可重复性)",
            "assertions": [
                "result1 == result2 for same seed",
                "random seed controls all stochastic elements",
            ],
        },
        {
            "name": "test_parameter_sweep",
            "description": "Parameter sweep produces monotonic trends",
            "assertions": [
                "metric changes monotonically with parameter",
                "no discontinuities in smooth parameter range",
            ],
        },
    ],
    "design": [
        {
            "name": "test_design_constraints_satisfied",
            "description": "Design output meets all constraints (设计约束)",
            "assertions": [
                "capacity >= required capacity",
                "safety factor >= minimum",
                "all dimensions within standard range",
            ],
        },
        {
            "name": "test_design_sensitivity",
            "description": "Design robust to parameter perturbation",
            "assertions": [
                "10% parameter change causes <20% output change",
                "no constraint violations under perturbation",
            ],
        },
    ],
    "operations": [
        {
            "name": "test_realtime_response",
            "description": "Response within latency budget (运维实时性)",
            "assertions": [
                "execution_time < max_latency",
                "result available before next cycle",
            ],
        },
        {
            "name": "test_alarm_accuracy",
            "description": "Alarm triggers correctly (运维告警准确性)",
            "assertions": [
                "true positive rate >= threshold",
                "false positive rate <= threshold",
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# DevTesterAgent
# ---------------------------------------------------------------------------

class DevTesterAgent(BaseAgent):
    """Development Tester — test generation, coverage analysis, execution.
    开发测试 Agent — 测试生成、覆盖分析、执行。
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_capabilities(self) -> list[str]:
        return ["test_generation", "coverage_analysis", "test_validation", "scenario_testing"]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        action = message.content.get("action", "generate_test_suite")
        params = message.content.get("params", {})
        if action == "generate_test_suite":
            suite = self.generate_test_suite(
                params.get("module", ""),
                params.get("functions"),
                params.get("scenario"),
            )
            return message.reply(suite.to_dict())
        elif action == "analyse_coverage":
            result = self.analyse_coverage(
                params.get("source_files", []),
                params.get("test_files", []),
            )
            return message.reply(result)
        elif action == "validate_test_result":
            report = DevTestReport(**params.get("report", {}))
            result = self.validate_test_result(report, params.get("criteria"))
            return message.reply(result)
        else:
            return message.error_reply(f"Unknown tester action: {action}")

    def generate_test_suite(
        self,
        module: str,
        functions: list[str] | None = None,
        scenario: str | None = None,
    ) -> DevTestSuite:
        """Generate a test suite for a module.
        为模块生成测试套件。

        Args:
            module: target module name (e.g. "simulation", "water_balance")
            functions: specific functions to test (optional)
            scenario: scenario type: "research", "design", "operations"

        Returns:
            DevTestSuite with generated test cases.
        """
        suite = DevTestSuite(
            name=f"test_{module}",
            category="unit" if not scenario else scenario,
        )

        # Module-level tests
        templates = MODULE_TEST_TEMPLATES.get(module, [])
        func_list = functions or [module]

        case_id = 1
        for func in func_list:
            for tmpl in templates:
                case = DevTestCase(
                    id=f"TC-{module[:3].upper()}-{case_id:03d}",
                    name=tmpl["name"].format(func=func),
                    description=tmpl["description"],
                    category="unit",
                    target_module=module,
                    target_function=func,
                    assertions=list(tmpl["assertions"]),
                )
                suite.add_case(case)
                case_id += 1

        # Scenario-level tests
        if scenario and scenario in SCENARIO_TEST_TEMPLATES:
            for tmpl in SCENARIO_TEST_TEMPLATES[scenario]:
                case = DevTestCase(
                    id=f"TC-{scenario[:3].upper()}-{case_id:03d}",
                    name=tmpl["name"],
                    description=tmpl["description"],
                    category=scenario,
                    target_module=module,
                    assertions=list(tmpl["assertions"]),
                    priority="high",
                )
                suite.add_case(case)
                case_id += 1

        logger.info(
            "DevTester: generated %d test cases for %s (scenario=%s)",
            len(suite.test_cases), module, scenario,
        )
        return suite

    def generate_scenario_tests(
        self,
        system: str,
        scenario: str,
    ) -> DevTestSuite:
        """Generate scenario-specific tests (科研/设计/运维).
        生成场景化测试（科研/设计/运维）。

        Args:
            system: "tank" (双容水箱) or "alumina" (氧化铝)
            scenario: "research", "design", or "operations"

        Returns:
            DevTestSuite with scenario test cases.
        """
        modules = self._get_modules_for_scenario(system, scenario)
        suite = DevTestSuite(
            name=f"test_{system}_{scenario}",
            category=scenario,
        )

        case_id = 1
        for mod in modules:
            mod_suite = self.generate_test_suite(mod, scenario=scenario)
            for case in mod_suite.test_cases:
                case.id = f"TC-{system[:3].upper()}-{scenario[:3].upper()}-{case_id:03d}"
                suite.add_case(case)
                case_id += 1

        return suite

    def analyse_coverage(
        self,
        source_files: list[str],
        test_files: list[str],
    ) -> dict:
        """Analyse test coverage gaps.
        分析测试覆盖缺口。

        Args:
            source_files: list of source file paths
            test_files: list of test file paths

        Returns:
            Coverage analysis report dict.
        """
        covered = set()
        uncovered = set()

        test_names = {
            tf.rsplit("/", 1)[-1].replace(".py", "").replace("test_", "")
            for tf in test_files
        }

        for sf in source_files:
            basename = sf.rsplit("/", 1)[-1].replace(".py", "")
            if basename.startswith("__"):
                continue
            if basename in test_names:
                covered.add(basename)
            else:
                uncovered.add(basename)

        total = len(covered) + len(uncovered)
        return {
            "total_modules": total,
            "covered_modules": len(covered),
            "uncovered_modules": len(uncovered),
            "coverage_rate": (
                len(covered) / total if total > 0 else 1.0
            ),
            "covered": sorted(covered),
            "uncovered": sorted(uncovered),
            "recommendation": self._coverage_recommendation(
                len(covered), len(uncovered),
            ),
        }

    def validate_test_result(
        self, report: DevTestReport, criteria: dict | None = None,
    ) -> dict:
        """Validate test execution results against criteria.
        根据标准验证测试执行结果。

        Args:
            report: DevTestReport from test execution
            criteria: pass criteria (default: all tests pass)

        Returns:
            Validation result dict.
        """
        criteria = criteria or {
            "min_pass_rate": 1.0,
            "max_failures": 0,
            "required_total": 1,
        }

        issues = []
        if report.pass_rate < criteria["min_pass_rate"]:
            issues.append(
                f"Pass rate {report.pass_rate:.2%} below "
                f"required {criteria['min_pass_rate']:.2%}"
            )
        if report.failed > criteria["max_failures"]:
            issues.append(
                f"{report.failed} failures exceed "
                f"max allowed {criteria['max_failures']}"
            )
        if report.total < criteria["required_total"]:
            issues.append(
                f"Only {report.total} tests, "
                f"need at least {criteria['required_total']}"
            )

        return {
            "valid": len(issues) == 0,
            "report": report.to_dict(),
            "criteria": criteria,
            "issues": issues,
        }

    # ----- private helpers -----

    @staticmethod
    def _get_modules_for_scenario(system: str, scenario: str) -> list[str]:
        """Get relevant modules for a system+scenario combination."""
        if system == "tank":
            base = ["simulation", "control"]
            if scenario == "research":
                return base + ["evaluation", "odd"]
            if scenario == "design":
                return base + ["design", "odd"]
            if scenario == "operations":
                return base + ["odd"]
        elif system == "alumina":
            base = ["water_balance", "evaporation"]
            if scenario == "research":
                return base + ["detection", "evaluation"]
            if scenario == "design":
                return base + ["design", "odd"]
            if scenario == "operations":
                return base + ["detection", "odd"]
        return ["simulation"]

    @staticmethod
    def _coverage_recommendation(covered: int, uncovered: int) -> str:
        total = covered + uncovered
        if total == 0:
            return "No modules found"
        rate = covered / total
        if rate >= 0.9:
            return "Excellent coverage"
        if rate >= 0.7:
            return "Good coverage, consider adding tests for uncovered modules"
        if rate >= 0.5:
            return "Moderate coverage, prioritize testing core modules"
        return "Low coverage, significant testing effort needed"
