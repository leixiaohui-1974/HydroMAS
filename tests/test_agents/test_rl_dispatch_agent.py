"""Phase 3 tests for the RL Dispatch Agent.
Phase 3 强化学习调度 Agent 测试。

Tests cover DispatchState / DispatchAction dataclasses, agent
initialization, rule-based action generation, evaluation, and
graceful degradation when torch is unavailable.
"""

import pytest

from agents.rl_dispatch_agent import DispatchAction, DispatchState, RLDispatchAgent


class TestDispatchState:
    """Test DispatchState dataclass defaults and methods."""

    def test_dispatch_state_defaults(self):
        """DispatchState default fields are correct types and values."""
        state = DispatchState()
        assert state.tank_levels == []
        assert state.demands == []
        assert state.electricity_price == 0.5
        assert state.hour_of_day == 0
        assert state.weather == {}

    def test_dispatch_state_to_vector(self):
        """to_vector() produces a flat numeric list."""
        state = DispatchState(
            tank_levels=[2.0, 3.0],
            demands=[100.0, 150.0],
            electricity_price=0.65,
            hour_of_day=12,
            weather={"temperature": 30.0, "humidity": 70.0},
        )
        vec = state.to_vector()
        assert isinstance(vec, list)
        assert all(isinstance(v, float) for v in vec)
        # Should contain: 2 tank_levels + 2 demands + price +
        # hour_norm + temp_norm + humidity_norm = 8
        assert len(vec) == 8


class TestDispatchAction:
    """Test DispatchAction dataclass defaults."""

    def test_dispatch_action_defaults(self):
        """DispatchAction default fields are correct types and values."""
        action = DispatchAction()
        assert action.intake_flows == []
        assert action.pump_states == []
        assert action.valve_positions == []

    def test_dispatch_action_with_values(self):
        """DispatchAction can be created with custom values."""
        action = DispatchAction(
            intake_flows=[100.0, 200.0],
            pump_states=[True, False, True],
            valve_positions=[0.5, 0.8],
        )
        assert len(action.intake_flows) == 2
        assert action.pump_states[1] is False
        assert action.valve_positions[0] == 0.5


class TestRLDispatchAgent:
    """Test RLDispatchAgent initialization, actions, and evaluation."""

    def test_rl_dispatch_init(self):
        """RLDispatchAgent creates without error."""
        agent = RLDispatchAgent()
        assert agent.n_tanks == 3
        assert agent.n_sources == 2
        assert agent.n_pumps == 4
        assert agent.max_intake == 500.0
        assert agent._rl_model is None

    def test_rl_dispatch_get_action(self):
        """get_action() returns a DispatchAction from rule-based baseline."""
        agent = RLDispatchAgent()
        state = DispatchState(
            tank_levels=[2.0, 2.5, 3.0],
            demands=[80.0, 100.0, 120.0],
            electricity_price=0.35,
            hour_of_day=3,
            weather={"temperature": 20.0, "humidity": 50.0},
        )
        action = agent.get_action(state)
        assert isinstance(action, DispatchAction)
        assert len(action.intake_flows) == agent.n_sources
        assert len(action.pump_states) == agent.n_pumps
        assert all(isinstance(f, float) for f in action.intake_flows)
        assert all(isinstance(p, bool) for p in action.pump_states)
        # Intake flows should be non-negative and bounded
        for flow in action.intake_flows:
            assert 0 <= flow <= agent.max_intake

    def test_rl_dispatch_evaluate(self):
        """evaluate() returns an evaluation dict with expected keys."""
        agent = RLDispatchAgent()
        result = agent.evaluate(n_episodes=5)
        assert isinstance(result, dict)
        assert "n_episodes" in result
        assert result["n_episodes"] == 5
        assert "rule_based" in result
        assert "mean_cost" in result["rule_based"]
        assert "min_cost" in result["rule_based"]
        assert "max_cost" in result["rule_based"]
        assert result["rule_based"]["mean_cost"] >= 0
        # Without RL model loaded, rl_policy should be None
        assert result["rl_policy"] is None
        assert result["improvement_pct"] is None

    def test_rl_dispatch_train_no_torch(self):
        """train() without torch gracefully returns skipped status."""
        agent = RLDispatchAgent()
        if agent._has_rl:
            pytest.skip("torch/stable-baselines3 available -- not testing fallback")
        result = agent.train(n_episodes=10)
        assert isinstance(result, dict)
        assert result["status"] == "skipped"
        assert "reason" in result
        assert "torch" in result["reason"] or "stable-baselines3" in result["reason"]
