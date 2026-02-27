"""Tests for DevTesterAgent."""

from __future__ import annotations

from agents.dev_tester import DevTestCase, DevTesterAgent, DevTestReport, DevTestSuite


class TestTestGeneration:
    """Test test case generation."""

    def setup_method(self):
        self.tester = DevTesterAgent()

    def test_generate_simulation_suite(self):
        suite = self.tester.generate_test_suite("simulation")
        assert suite.name == "test_simulation"
        assert len(suite.test_cases) > 0
        for tc in suite.test_cases:
            assert tc.target_module == "simulation"

    def test_generate_water_balance_suite(self):
        suite = self.tester.generate_test_suite("water_balance")
        assert len(suite.test_cases) > 0
        # Should include mass conservation test
        names = [tc.name for tc in suite.test_cases]
        assert any("conservation" in n for n in names)

    def test_generate_evaporation_suite(self):
        suite = self.tester.generate_test_suite("evaporation")
        assert len(suite.test_cases) > 0
        names = [tc.name for tc in suite.test_cases]
        assert any("merkel" in n for n in names)

    def test_generate_detection_suite(self):
        suite = self.tester.generate_test_suite("detection")
        assert len(suite.test_cases) > 0
        names = [tc.name for tc in suite.test_cases]
        assert any("leak" in n for n in names)

    def test_generate_odd_suite(self):
        suite = self.tester.generate_test_suite("odd")
        assert len(suite.test_cases) > 0
        names = [tc.name for tc in suite.test_cases]
        assert any("green" in n or "red" in n for n in names)

    def test_generate_control_suite(self):
        suite = self.tester.generate_test_suite("control")
        assert len(suite.test_cases) > 0
        names = [tc.name for tc in suite.test_cases]
        assert any("setpoint" in n for n in names)

    def test_generate_with_specific_functions(self):
        suite = self.tester.generate_test_suite(
            "simulation",
            functions=["run_simulation", "simulate_network"],
        )
        funcs = {tc.target_function for tc in suite.test_cases}
        assert "run_simulation" in funcs
        assert "simulate_network" in funcs

    def test_generate_with_scenario_research(self):
        suite = self.tester.generate_test_suite(
            "simulation", scenario="research"
        )
        categories = {tc.category for tc in suite.test_cases}
        assert "research" in categories
        names = [tc.name for tc in suite.test_cases]
        assert any("reproducibility" in n for n in names)

    def test_generate_with_scenario_design(self):
        suite = self.tester.generate_test_suite(
            "simulation", scenario="design"
        )
        names = [tc.name for tc in suite.test_cases]
        assert any("constraint" in n for n in names)

    def test_generate_with_scenario_operations(self):
        suite = self.tester.generate_test_suite(
            "simulation", scenario="operations"
        )
        names = [tc.name for tc in suite.test_cases]
        assert any("realtime" in n or "alarm" in n for n in names)

    def test_unknown_module_returns_empty(self):
        suite = self.tester.generate_test_suite("nonexistent_module")
        # No templates for unknown module, but scenario tests may apply
        assert suite.name == "test_nonexistent_module"


class TestScenarioTests:
    """Test scenario-based test generation."""

    def setup_method(self):
        self.tester = DevTesterAgent()

    def test_tank_research(self):
        suite = self.tester.generate_scenario_tests("tank", "research")
        assert suite.name == "test_tank_research"
        assert suite.category == "research"
        assert len(suite.test_cases) > 0

    def test_tank_design(self):
        suite = self.tester.generate_scenario_tests("tank", "design")
        assert len(suite.test_cases) > 0

    def test_tank_operations(self):
        suite = self.tester.generate_scenario_tests("tank", "operations")
        assert len(suite.test_cases) > 0

    def test_alumina_research(self):
        suite = self.tester.generate_scenario_tests("alumina", "research")
        assert len(suite.test_cases) > 0
        modules = {tc.target_module for tc in suite.test_cases}
        assert "water_balance" in modules or "evaporation" in modules

    def test_alumina_design(self):
        suite = self.tester.generate_scenario_tests("alumina", "design")
        assert len(suite.test_cases) > 0

    def test_alumina_operations(self):
        suite = self.tester.generate_scenario_tests("alumina", "operations")
        assert len(suite.test_cases) > 0


class TestCoverageAnalysis:
    """Test coverage analysis."""

    def setup_method(self):
        self.tester = DevTesterAgent()

    def test_full_coverage(self):
        result = self.tester.analyse_coverage(
            source_files=["core/simulation.py", "core/control.py"],
            test_files=[
                "tests/test_simulation.py",
                "tests/test_control.py",
            ],
        )
        assert result["coverage_rate"] == 1.0
        assert result["uncovered_modules"] == 0

    def test_partial_coverage(self):
        result = self.tester.analyse_coverage(
            source_files=[
                "core/simulation.py",
                "core/control.py",
                "core/new_module.py",
            ],
            test_files=["tests/test_simulation.py"],
        )
        assert 0 < result["coverage_rate"] < 1.0
        assert "new_module" in result["uncovered"]

    def test_no_sources(self):
        result = self.tester.analyse_coverage([], [])
        assert result["total_modules"] == 0
        assert result["coverage_rate"] == 1.0

    def test_init_files_excluded(self):
        result = self.tester.analyse_coverage(
            source_files=["core/__init__.py", "core/sim.py"],
            test_files=["tests/test_sim.py"],
        )
        # __init__ should be excluded
        assert result["total_modules"] == 1


class TestResultValidation:
    """Test result validation."""

    def setup_method(self):
        self.tester = DevTesterAgent()

    def test_all_passed_valid(self):
        report = DevTestReport(
            suite_name="test_suite",
            total=10,
            passed=10,
            failed=0,
        )
        result = self.tester.validate_test_result(report)
        assert result["valid"]
        assert len(result["issues"]) == 0

    def test_failures_invalid(self):
        report = DevTestReport(
            suite_name="test_suite",
            total=10,
            passed=8,
            failed=2,
        )
        result = self.tester.validate_test_result(report)
        assert not result["valid"]

    def test_custom_criteria(self):
        report = DevTestReport(
            suite_name="test_suite",
            total=10,
            passed=9,
            failed=1,
        )
        # Allow up to 1 failure
        result = self.tester.validate_test_result(
            report,
            criteria={"min_pass_rate": 0.8, "max_failures": 1, "required_total": 5},
        )
        assert result["valid"]


class TestDataClasses:
    """Test data class serialization."""

    def test_test_case_to_dict(self):
        tc = DevTestCase(
            id="TC-001",
            name="test_example",
            description="Example test",
            target_module="simulation",
        )
        d = tc.to_dict()
        assert d["id"] == "TC-001"
        assert d["name"] == "test_example"

    def test_test_suite_to_dict(self):
        suite = DevTestSuite(name="test_suite")
        suite.add_case(DevTestCase(
            id="TC-001", name="test_1", description="Test 1",
        ))
        d = suite.to_dict()
        assert d["test_count"] == 1
        assert len(d["test_cases"]) == 1

    def test_test_report_pass_rate(self):
        report = DevTestReport(
            suite_name="x", total=10, passed=7, failed=3,
        )
        assert report.pass_rate == 0.7
        assert not report.all_passed

    def test_test_report_all_passed(self):
        report = DevTestReport(
            suite_name="x", total=5, passed=5, failed=0,
        )
        assert report.all_passed
