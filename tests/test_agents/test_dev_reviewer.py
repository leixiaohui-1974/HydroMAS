"""Tests for DevReviewerAgent."""

from __future__ import annotations

from agents.dev_reviewer import DevReviewerAgent, ReviewComment


class TestCodeReview:
    """Test code review functionality."""

    def setup_method(self):
        self.reviewer = DevReviewerAgent()

    def test_clean_code_approved(self):
        """Clean code should be approved."""
        files = {
            "core/example.py": (
                '"""Example module."""\n'
                '\n'
                'def calculate(x: float) -> float:\n'
                '    """Calculate something."""\n'
                '    return x * 2\n'
            ),
        }
        result = self.reviewer.review_code(files)
        assert result.approved

    def test_architecture_violation_core_imports_agents(self):
        """Core importing from agents is an architecture violation."""
        files = {
            "core/simulation/bad.py": (
                'from agents.orchestrator import OrchestratorAgent\n'
                'x = 1\n'
            ),
        }
        result = self.reviewer.review_code(files)
        arch_errors = [
            c for c in result.comments
            if c.category == "architecture"
            and c.severity == "error"
        ]
        assert len(arch_errors) > 0

    def test_safety_hardcoded_password(self):
        """Hardcoded password should be flagged."""
        files = {
            "web/config.py": (
                "password = 'super_secret_123'\n"
            ),
        }
        result = self.reviewer.review_code(files)
        safety_errors = [
            c for c in result.comments
            if c.category == "safety"
            and c.severity == "error"
        ]
        assert len(safety_errors) > 0
        assert not result.approved

    def test_safety_eval_usage(self):
        """eval() usage should be flagged as warning."""
        files = {
            "core/calc.py": (
                "result = eval(user_input)\n"
            ),
        }
        result = self.reviewer.review_code(files)
        eval_warnings = [
            c for c in result.comments
            if "eval" in c.message.lower()
        ]
        assert len(eval_warnings) > 0

    def test_scores_calculated(self):
        """Review should produce scores for each dimension."""
        files = {
            "core/example.py": "x = 1\n",
        }
        result = self.reviewer.review_code(files)
        assert "architecture" in result.scores
        assert "safety" in result.scores
        assert "style" in result.scores
        assert "domain" in result.scores
        assert "overall" in result.scores

    def test_to_dict(self):
        """ReviewResult.to_dict() produces complete dict."""
        files = {"core/x.py": "x = 1\n"}
        result = self.reviewer.review_code(files)
        d = result.to_dict()
        assert "approved" in d
        assert "comments" in d
        assert "scores" in d
        assert "error_count" in d


class TestDesignReview:
    """Test design document review."""

    def setup_method(self):
        self.reviewer = DevReviewerAgent()

    def test_complete_design_passes(self):
        design = {
            "requirement": {
                "acceptance_criteria": ["Tests pass"],
            },
            "implementation_plan": {
                "tasks": [
                    {"id": "impl", "description": "Implement"},
                    {"id": "test_1", "description": "Write tests"},
                    {"id": "review_1", "description": "Review"},
                ],
            },
            "risk_notes": "Low risk",
        }
        result = self.reviewer.review_design(design)
        assert result.approved

    def test_missing_tests_flagged(self):
        design = {
            "requirement": {"acceptance_criteria": ["Works"]},
            "implementation_plan": {
                "tasks": [
                    {"id": "impl", "description": "Implement"},
                ],
            },
            "risk_notes": "Low",
        }
        result = self.reviewer.review_design(design)
        messages = [c.message for c in result.comments]
        assert any("no test tasks" in m.lower() for m in messages)

    def test_missing_review_flagged(self):
        design = {
            "requirement": {"acceptance_criteria": ["Works"]},
            "implementation_plan": {
                "tasks": [
                    {"id": "impl", "description": "Implement"},
                    {"id": "test_1", "description": "Test"},
                ],
            },
            "risk_notes": "Low",
        }
        result = self.reviewer.review_design(design)
        messages = [c.message for c in result.comments]
        assert any("no review tasks" in m.lower() for m in messages)

    def test_missing_acceptance_criteria(self):
        design = {
            "requirement": {},
            "implementation_plan": {
                "tasks": [
                    {"id": "test_1"},
                    {"id": "review_1"},
                ],
            },
        }
        result = self.reviewer.review_design(design)
        messages = [c.message for c in result.comments]
        assert any("acceptance criteria" in m.lower() for m in messages)


class TestReviewComment:
    """Test ReviewComment data class."""

    def test_to_dict(self):
        c = ReviewComment(
            file="test.py",
            line=10,
            severity="error",
            category="safety",
            message="Found issue",
        )
        d = c.to_dict()
        assert d["file"] == "test.py"
        assert d["line"] == 10
        assert d["severity"] == "error"


class TestTestCoverageCheck:
    """Test the test coverage checking functionality."""

    def setup_method(self):
        self.reviewer = DevReviewerAgent()

    def test_coverage_check_with_tests(self):
        source = {"core/calc.py": "def calc(): pass\n"}
        tests = {
            "tests/test_calc.py": "def test_calc_basic(): pass\n"
        }
        result = self.reviewer.review_code(
            source, context={"test_files": tests}
        )
        # Should have no coverage warnings since test_calc matches calc
        coverage_warnings = [
            c for c in result.comments
            if c.category == "test_coverage"
        ]
        assert len(coverage_warnings) == 0

    def test_coverage_check_missing_test(self):
        source = {"core/calc.py": "def calc(): pass\n"}
        tests = {
            "tests/test_other.py": "def test_other(): pass\n"
        }
        result = self.reviewer.review_code(
            source, context={"test_files": tests}
        )
        coverage_warnings = [
            c for c in result.comments
            if c.category == "test_coverage"
        ]
        assert len(coverage_warnings) > 0
