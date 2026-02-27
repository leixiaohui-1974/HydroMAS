"""R1: 双容水箱科研场景 — PID/MPC对比论文工作流。
写作 + 建模 + 管理 = 科研

验证点：仿真可重复、控制器性能评估、ODD安全分析、报告生成。
"""

from __future__ import annotations

from core.config import get_default_tank_params
from core.control import MPCController, PIDController, PIDParams
from core.evaluation import evaluate_performance
from core.odd import check_odd
from core.simulation import run_simulation


class TestResearchTankSimulation:
    """R1-T1: 仿真参数可配置，结果可重复。"""

    def test_default_params_loadable(self):
        params = get_default_tank_params()
        assert "area" in params
        assert "cd" in params

    def test_simulation_produces_output(self):
        result = run_simulation(
            duration=10,
            dt=0.1,
            q_in_profile=[(0.0, 0.5), (10.0, 0.5)],
            initial_h=0.5,
            tank_params={"area": 1.0, "cd": 0.6},
        )
        assert "time" in result
        assert "water_level" in result
        assert len(result["water_level"]) > 0

    def test_simulation_reproducibility(self):
        """同一参数两次仿真结果相同（科研可重复性）。"""
        kwargs = dict(
            duration=10,
            dt=0.1,
            q_in_profile=[(0.0, 0.5), (10.0, 0.5)],
            initial_h=0.5,
            tank_params={"area": 1.0, "cd": 0.6},
        )
        r1 = run_simulation(**kwargs)
        r2 = run_simulation(**kwargs)
        assert r1["water_level"] == r2["water_level"]

    def test_level_non_negative(self):
        """水位物理约束：不能为负。"""
        result = run_simulation(
            duration=5,
            dt=0.1,
            q_in_profile=[(0.0, 0.0), (5.0, 0.0)],
            initial_h=0.0,
            tank_params={"area": 1.0, "cd": 0.6},
        )
        assert all(h >= 0 for h in result["water_level"])


class TestResearchTankControl:
    """R1-T2: PID/MPC控制器在ODD边界内。"""

    def test_pid_controller_exists(self):
        pid = PIDController(PIDParams(kp=1.0, ki=0.1, kd=0.05))
        assert pid is not None
        output = pid.compute(setpoint=1.0, measured=0.5, dt=0.1)
        assert isinstance(output, (int, float))

    def test_mpc_controller_exists(self):
        mpc = MPCController(horizon=10, dt=0.1)
        assert mpc is not None

    def test_pid_output_bounded(self):
        """PID输出不应发散。"""
        pid = PIDController(PIDParams(kp=1.0, ki=0.1, kd=0.05))
        outputs = []
        measured = 0.0
        for _ in range(50):
            u = pid.compute(setpoint=1.0, measured=measured, dt=0.1)
            outputs.append(u)
            measured += u * 0.01  # 简化响应
        # 输出应该是有界的
        assert all(abs(o) < 1000 for o in outputs)


class TestResearchTankEvaluation:
    """R1-T3: 性能评估指标正确计算。"""

    def test_evaluate_performance_basic(self):
        result = run_simulation(
            duration=10,
            dt=0.1,
            q_in_profile=[(0.0, 0.5), (10.0, 0.5)],
            initial_h=0.5,
            tank_params={"area": 1.0, "cd": 0.6},
        )
        # evaluate_performance expects (observed, predicted) lists
        water_levels = result["water_level"]
        # Use a simple reference (constant setpoint) as observed
        setpoint = [0.5] * len(water_levels)
        metrics = evaluate_performance(setpoint, water_levels)
        assert isinstance(metrics, dict)
        assert len(metrics) > 0


class TestResearchTankODD:
    """R1-T4: ODD安全边界分析。"""

    def test_normal_state_normal(self):
        result = check_odd({"water_level": 0.5})
        assert result["zone"] == "normal"

    def test_extreme_state_not_normal(self):
        result = check_odd({"water_level": 100.0})
        assert result["zone"] != "normal"


class TestResearchTankReport:
    """R1-T5: 报告生成功能。"""

    def test_report_agent_generates_markdown(self):
        from agents.report_agent import ReportAgent

        agent = ReportAgent()
        report = agent.generate_control_report({
            "controller_type": "PID",
            "performance_metrics": {"settling_time": 5.0, "overshoot": 0.1},
            "control_simulation": {},
        })
        assert isinstance(report, str)
        assert "PID" in report
