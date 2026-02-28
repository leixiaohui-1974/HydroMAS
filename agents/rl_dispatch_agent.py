"""RL Dispatch Agent -- reinforcement learning water scheduling.
强化学习调度 Agent -- 基于数字孪生的水量优化调度。

Uses a digital twin simulation environment to train and evaluate
reinforcement learning policies for optimal water intake scheduling.
When torch / stable-baselines3 / gymnasium are not available, falls
back to a rule-based heuristic baseline.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

from agents.base_agent import BaseAgent
from agents.message import AgentMessage, MessageType

logger = logging.getLogger(__name__)


@dataclass
class DispatchState:
    """Observable state for the dispatch environment.
    调度环境的可观测状态。

    Attributes:
        tank_levels: Water levels for each tank (m) / 各水池液位
        demands: Current water demands per workshop (m3/h) / 各车间需水量
        electricity_price: Current electricity price (CNY/kWh) / 当前电价
        hour_of_day: Hour of day (0-23) / 当天小时
        weather: Weather features (temperature, humidity, etc.) / 气象特征
    """

    tank_levels: list[float] = field(default_factory=list)
    demands: list[float] = field(default_factory=list)
    electricity_price: float = 0.5
    hour_of_day: int = 0
    weather: dict[str, float] = field(default_factory=dict)

    def to_vector(self) -> list[float]:
        """Flatten state to a numeric vector for RL input.
        将状态展平为数值向量供RL输入。
        """
        vec = list(self.tank_levels) + list(self.demands)
        vec.append(self.electricity_price)
        vec.append(float(self.hour_of_day) / 23.0)  # Normalise to [0, 1]
        vec.append(self.weather.get("temperature", 25.0) / 50.0)
        vec.append(self.weather.get("humidity", 60.0) / 100.0)
        return vec


@dataclass
class DispatchAction:
    """Action output for the dispatch agent.
    调度 Agent 的动作输出。

    Attributes:
        intake_flows: Intake flow rates per source (m3/h) / 各取水源流量
        pump_states: On/off states for pumps / 泵开关状态
        valve_positions: Valve positions [0-1] / 阀门开度
    """

    intake_flows: list[float] = field(default_factory=list)
    pump_states: list[bool] = field(default_factory=list)
    valve_positions: list[float] = field(default_factory=list)


class RLDispatchAgent(BaseAgent):
    """Reinforcement Learning Dispatch Agent.
    强化学习调度 Agent。

    When torch and stable-baselines3 are available, uses PPO to learn
    an optimal dispatch policy.  Otherwise, provides a deterministic
    rule-based baseline that keeps tank levels near their setpoints
    while minimising electricity cost.
    """

    def __init__(
        self,
        twin_engine: Any | None = None,
        model_path: str | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.twin_engine = twin_engine
        self.model_path = model_path
        self._rl_model: Any | None = None
        self._gym_env: Any | None = None
        self._has_rl = False

        # Default configuration
        self.n_tanks: int = 3
        self.n_sources: int = 2
        self.n_pumps: int = 4
        self.tank_setpoints: list[float] = [3.0, 3.0, 3.0]
        self.tank_max: list[float] = [5.0, 5.0, 5.0]
        self.tank_min: list[float] = [0.5, 0.5, 0.5]
        self.max_intake: float = 500.0  # m3/h per source

        self._try_load_rl(model_path)

    def get_capabilities(self) -> list[str]:
        return ["rl_dispatch", "water_scheduling", "policy_training", "policy_evaluation"]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        action = message.content.get("action", "get_action")
        params = message.content.get("params", {})
        if action == "get_action":
            state = DispatchState(**params) if isinstance(params, dict) else params
            result = self.get_action(state)
            return message.reply({
                "intake_flows": result.intake_flows,
                "pump_states": result.pump_states,
                "valve_positions": result.valve_positions,
            })
        elif action == "evaluate":
            result = self.evaluate(params.get("n_episodes", 100))
            return message.reply(result)
        elif action == "train":
            result = self.train(params.get("n_episodes", 1000), params.get("save_path"))
            return message.reply(result)
        else:
            return message.error_reply(f"Unknown dispatch action: {action}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_action(self, state: DispatchState) -> DispatchAction:
        """Get dispatch action for the given state.
        根据当前状态获取调度动作。

        When an RL model is loaded, uses it for inference; otherwise
        falls back to the rule-based baseline.

        Args:
            state: Current dispatch state / 当前调度状态

        Returns:
            DispatchAction with intake flows, pump states, valve positions.
        """
        if self._rl_model is not None:
            return self._rl_action(state)
        return self._rule_based_action(state)

    def train(self, n_episodes: int = 1000, save_path: str | None = None) -> dict:
        """Train the RL dispatch policy.
        训练RL调度策略。

        Args:
            n_episodes: Number of training episodes / 训练轮数
            save_path: Path to save trained model / 模型保存路径

        Returns:
            Training summary dict with metrics.
        """
        if not self._has_rl:
            return {
                "status": "skipped",
                "reason": "torch/stable-baselines3/gymnasium not available",
                "suggestion": "pip install torch stable-baselines3 gymnasium",
            }

        env = self._build_gym_env()
        if env is None:
            return {"status": "error", "reason": "Failed to build gym environment"}

        try:
            from stable_baselines3 import PPO  # type: ignore

            model = PPO(
                "MlpPolicy",
                env,
                verbose=1,
                n_steps=256,
                batch_size=64,
                learning_rate=3e-4,
            )
            total_timesteps = n_episodes * 24  # 24 steps per episode (hourly)
            model.learn(total_timesteps=total_timesteps)

            if save_path:
                model.save(save_path)
                logger.info("RL model saved to %s", save_path)

            self._rl_model = model
            return {
                "status": "completed",
                "n_episodes": n_episodes,
                "total_timesteps": total_timesteps,
                "save_path": save_path,
            }
        except Exception as exc:
            logger.error("RL training failed: %s", exc, exc_info=True)
            return {"status": "error", "reason": str(exc)}

    def evaluate(self, n_episodes: int = 100) -> dict:
        """Evaluate the current dispatch policy.
        评估当前调度策略。

        Compares RL policy (if available) against the rule-based baseline
        over *n_episodes* simulated days.

        Args:
            n_episodes: Number of evaluation episodes / 评估轮数

        Returns:
            Evaluation summary with cost, constraint violations, etc.
        """
        rule_costs: list[float] = []
        rl_costs: list[float] = []

        for ep in range(n_episodes):
            state = self._make_random_state(ep)
            # Rule-based cost
            action = self._rule_based_action(state)
            rule_cost = self._estimate_cost(state, action)
            rule_costs.append(rule_cost)

            # RL cost (if model available)
            if self._rl_model is not None:
                rl_action = self._rl_action(state)
                rl_cost = self._estimate_cost(state, rl_action)
                rl_costs.append(rl_cost)

        result: dict[str, Any] = {
            "n_episodes": n_episodes,
            "rule_based": {
                "mean_cost": sum(rule_costs) / len(rule_costs) if rule_costs else 0,
                "min_cost": min(rule_costs) if rule_costs else 0,
                "max_cost": max(rule_costs) if rule_costs else 0,
            },
        }

        if rl_costs:
            result["rl_policy"] = {
                "mean_cost": sum(rl_costs) / len(rl_costs),
                "min_cost": min(rl_costs),
                "max_cost": max(rl_costs),
            }
            improvement = (
                (result["rule_based"]["mean_cost"] - result["rl_policy"]["mean_cost"])
                / result["rule_based"]["mean_cost"]
                * 100
                if result["rule_based"]["mean_cost"] > 0
                else 0
            )
            result["improvement_pct"] = round(improvement, 2)
        else:
            result["rl_policy"] = None
            result["improvement_pct"] = None

        return result

    # ------------------------------------------------------------------
    # Gym environment
    # ------------------------------------------------------------------

    def _build_gym_env(self) -> Any | None:
        """Build a Gymnasium environment wrapping the digital twin.
        构建包装数字孪生的Gymnasium环境。
        """
        try:
            import gymnasium as gym  # type: ignore
            import numpy as np  # type: ignore
        except ImportError:
            logger.warning("gymnasium/numpy not available -- cannot build env")
            return None

        agent_ref = self

        class WaterDispatchEnv(gym.Env):  # type: ignore[misc]
            """Custom Gymnasium environment for water dispatch."""

            metadata = {"render_modes": []}

            def __init__(self) -> None:
                super().__init__()
                # levels + demands + price + hour + temp + humidity
                obs_dim = (
                    agent_ref.n_tanks + agent_ref.n_tanks + 4
                )
                act_dim = agent_ref.n_sources + agent_ref.n_pumps
                self.observation_space = gym.spaces.Box(
                    low=-1.0, high=1.0, shape=(obs_dim,), dtype=np.float32,
                )
                self.action_space = gym.spaces.Box(
                    low=0.0, high=1.0, shape=(act_dim,), dtype=np.float32,
                )
                self._step_count = 0
                self._state: DispatchState | None = None

            def reset(self, *, seed: int | None = None, options: dict | None = None) -> tuple:
                super().reset(seed=seed)
                self._step_count = 0
                self._state = agent_ref._make_random_state(seed or 0)
                obs = np.array(self._state.to_vector(), dtype=np.float32)
                # Pad / truncate to obs_dim
                obs_dim = self.observation_space.shape[0]
                if len(obs) < obs_dim:
                    obs = np.concatenate([obs, np.zeros(obs_dim - len(obs), dtype=np.float32)])
                else:
                    obs = obs[:obs_dim]
                return obs, {}

            def step(self, action: Any) -> tuple:
                self._step_count += 1
                # Decode action
                intake_flows = [
                    float(action[i]) * agent_ref.max_intake
                    for i in range(agent_ref.n_sources)
                ]
                pump_states = [
                    bool(action[agent_ref.n_sources + i] > 0.5)
                    for i in range(agent_ref.n_pumps)
                ]
                da = DispatchAction(
                    intake_flows=intake_flows,
                    pump_states=pump_states,
                    valve_positions=[],
                )

                # Simple reward: negative cost + penalty for constraint violations
                cost = agent_ref._estimate_cost(self._state, da)  # type: ignore[arg-type]
                penalty = 0.0
                if self._state is not None:
                    for i, lvl in enumerate(self._state.tank_levels):
                        if lvl < agent_ref.tank_min[i]:
                            penalty += 10.0
                        elif lvl > agent_ref.tank_max[i]:
                            penalty += 10.0

                reward = -(cost + penalty)
                terminated = self._step_count >= 24
                truncated = False

                # Advance state
                if self._state is not None:
                    new_hour = (self._state.hour_of_day + 1) % 24
                    new_levels = []
                    for i, lvl in enumerate(self._state.tank_levels):
                        inflow = sum(intake_flows) / max(agent_ref.n_tanks, 1)
                        outflow = self._state.demands[i] if i < len(self._state.demands) else 0
                        new_lvl = lvl + (inflow - outflow) * 1.0 / 1000.0  # simplified
                        new_levels.append(max(0.0, new_lvl))
                    self._state = DispatchState(
                        tank_levels=new_levels,
                        demands=self._state.demands,
                        electricity_price=self._state.electricity_price,
                        hour_of_day=new_hour,
                        weather=self._state.weather,
                    )

                obs = np.array(self._state.to_vector() if self._state else [], dtype=np.float32)
                obs_dim = self.observation_space.shape[0]
                if len(obs) < obs_dim:
                    obs = np.concatenate([obs, np.zeros(obs_dim - len(obs), dtype=np.float32)])
                else:
                    obs = obs[:obs_dim]

                return obs, reward, terminated, truncated, {}

        return WaterDispatchEnv()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _try_load_rl(self, model_path: str | None) -> None:
        """Try to load RL dependencies and optionally a saved model."""
        try:
            import gymnasium  # noqa: F401
            import stable_baselines3  # noqa: F401
            import torch  # noqa: F401
            self._has_rl = True
            logger.info("RL dependencies available (torch, stable-baselines3, gymnasium)")
        except ImportError:
            self._has_rl = False
            logger.info("RL dependencies not available -- using rule-based baseline")

        if model_path and self._has_rl:
            try:
                from stable_baselines3 import PPO  # type: ignore
                self._rl_model = PPO.load(model_path)
                logger.info("Loaded RL model from %s", model_path)
            except Exception as exc:
                logger.warning("Failed to load RL model from %s: %s", model_path, exc)
                self._rl_model = None

    def _rule_based_action(self, state: DispatchState) -> DispatchAction:
        """Deterministic rule-based dispatch baseline.
        确定性规则基线调度。

        Strategy:
            - Keep each tank level near its setpoint.
            - Prefer pumping during off-peak hours (electricity_price < 0.5).
            - Distribute intake evenly across sources.
        """
        total_demand = sum(state.demands) if state.demands else 100.0
        total_deficit = 0.0
        for i, lvl in enumerate(state.tank_levels):
            sp = self.tank_setpoints[i] if i < len(self.tank_setpoints) else 3.0
            total_deficit += max(0.0, sp - lvl)

        # Scale intake by deficit and electricity price
        price_factor = 1.2 if state.electricity_price < 0.5 else 0.8
        base_intake = (total_demand + total_deficit * 50.0) * price_factor
        per_source = min(base_intake / max(self.n_sources, 1), self.max_intake)

        intake_flows = [per_source] * self.n_sources

        # Pumps: activate if demand > 0 and tank level below setpoint
        pump_states: list[bool] = []
        for i in range(self.n_pumps):
            tank_idx = i % self.n_tanks
            lvl = state.tank_levels[tank_idx] if tank_idx < len(state.tank_levels) else 0.0
            sp = self.tank_setpoints[tank_idx] if tank_idx < len(self.tank_setpoints) else 3.0
            pump_states.append(lvl < sp)

        # Valve positions proportional to demand
        valve_positions: list[float] = []
        max_demand = max(state.demands) if state.demands else 1.0
        for d in state.demands:
            valve_positions.append(min(1.0, d / max_demand) if max_demand > 0 else 0.5)

        return DispatchAction(
            intake_flows=intake_flows,
            pump_states=pump_states,
            valve_positions=valve_positions,
        )

    def _rl_action(self, state: DispatchState) -> DispatchAction:
        """Get action from the RL model."""
        import numpy as np  # type: ignore

        obs = np.array(state.to_vector(), dtype=np.float32)
        # Pad to match environment observation space
        expected_dim = self.n_tanks + self.n_tanks + 4
        if len(obs) < expected_dim:
            obs = np.concatenate([obs, np.zeros(expected_dim - len(obs), dtype=np.float32)])
        else:
            obs = obs[:expected_dim]

        action_raw, _ = self._rl_model.predict(obs, deterministic=True)

        intake_flows = [float(action_raw[i]) * self.max_intake for i in range(self.n_sources)]
        pump_states = [bool(action_raw[self.n_sources + i] > 0.5) for i in range(self.n_pumps)]

        return DispatchAction(
            intake_flows=intake_flows,
            pump_states=pump_states,
            valve_positions=[],
        )

    def _estimate_cost(self, state: DispatchState, action: DispatchAction) -> float:
        """Estimate hourly operational cost for an action.
        估算单步运行成本。
        """
        # Electricity cost for pumping
        pump_power_kw = 50.0  # Assumed per-pump power
        n_active_pumps = sum(1 for p in action.pump_states if p)
        elec_cost = n_active_pumps * pump_power_kw * state.electricity_price

        # Water intake cost
        water_price_per_m3 = 4.0
        total_intake = sum(action.intake_flows)
        water_cost = total_intake * water_price_per_m3

        return elec_cost + water_cost

    def _make_random_state(self, seed: int) -> DispatchState:
        """Create a pseudo-random state for evaluation (deterministic given seed).
        生成用于评估的伪随机状态（给定种子确定性）。
        """
        # Simple deterministic pseudo-random using seed
        def _pseudo(s: int, idx: int) -> float:
            return abs(math.sin(s * 7.3 + idx * 13.7)) % 1.0

        tank_levels = [
            self.tank_min[i] + _pseudo(seed, i) * (self.tank_max[i] - self.tank_min[i])
            for i in range(self.n_tanks)
        ]
        demands = [50.0 + _pseudo(seed, self.n_tanks + i) * 150.0 for i in range(self.n_tanks)]
        hour = int(_pseudo(seed, 100) * 24) % 24
        price = 0.35 if 0 <= hour <= 7 or hour >= 22 else 0.65
        temp = 15.0 + _pseudo(seed, 200) * 25.0
        humidity = 30.0 + _pseudo(seed, 300) * 60.0

        return DispatchState(
            tank_levels=tank_levels,
            demands=demands,
            electricity_price=price,
            hour_of_day=hour,
            weather={"temperature": temp, "humidity": humidity},
        )
