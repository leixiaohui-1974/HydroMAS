"""Analysis Agent — flexible data analysis and script generation.
分析 Agent — 灵活数据分析和脚本生成。

This agent represents the "flexible" layer of the architecture:
it can dynamically compose analysis workflows, generate comparison
scripts, and produce visualizations.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class AnalysisAgent:
    """Analysis Agent for flexible data analysis.
    灵活数据分析 Agent。

    Key capabilities:
        - Scheme comparison (A vs B with unified metrics)
        - Sensitivity analysis (auto-generate parameter sweeps)
        - Optimization (dynamically construct optimization problems)
        - Visualization (generate matplotlib/plotly code)
    """

    async def compare_schemes(
        self,
        schemes: list[dict],
        metrics: list[str] | None = None,
        weights: dict[str, float] | None = None,
    ) -> dict:
        """Compare multiple simulation schemes.
        比较多个仿真方案。

        Args:
            schemes: List of scheme configurations / 方案配置列表
            metrics: Metrics for comparison / 比较指标
            weights: Metric weights for ranking / 指标权重

        Returns:
            Comparison results with ranking.
        """
        from mcp_servers.simulation_server import simulate_tank

        if metrics is None:
            metrics = ["RMSE", "MAE"]
        if weights is None:
            weights = {m: 1.0 / len(metrics) for m in metrics}

        async def _run_one(i: int, scheme: dict) -> dict:
            sim = await asyncio.to_thread(simulate_tank, **scheme)
            levels = sim.get("water_level") or [0.0]
            return {
                "scheme_index": i,
                "scheme": scheme,
                "simulation": sim,
                "max_level": max(levels),
                "min_level": min(levels),
                "final_level": levels[-1],
            }

        results = await asyncio.gather(*[_run_one(i, s) for i, s in enumerate(schemes)])

        results = list(results)
        # Rank schemes
        ranking = sorted(results, key=lambda r: r["final_level"], reverse=True)
        for rank, r in enumerate(ranking):
            r["rank"] = rank + 1

        return {
            "results": results,
            "ranking": [r["scheme_index"] for r in ranking],
            "n_schemes": len(schemes),
        }

    async def generate_visualization_code(
        self,
        data: dict,
        plot_type: str = "time_series",
    ) -> str:
        """Generate matplotlib visualization code for given data.
        为给定数据生成 matplotlib 可视化代码。

        Args:
            data: Data to visualize / 待可视化数据
            plot_type: Type of plot / 图表类型

        Returns:
            Python code string for visualization.
        """
        if plot_type == "time_series":
            code = """
import matplotlib.pyplot as plt

time = {time}
water_level = {water_level}

fig, ax = plt.subplots(figsize=(10, 6))
ax.plot(time, water_level, 'b-', linewidth=1.5)
ax.set_xlabel('Time (s)')
ax.set_ylabel('Water Level (m)')
ax.set_title('Tank Water Level Over Time')
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('water_level.png', dpi=150)
plt.show()
""".format(
                time=data.get("time", []),
                water_level=data.get("water_level", []),
            )
            return code

        elif plot_type == "control_comparison":
            code = """
import matplotlib.pyplot as plt

fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

# Water level
for label, result in results.items():
    axes[0].plot(result['time'], result['water_level'], label=label)
axes[0].axhline(y=setpoint, color='r', linestyle='--', label='Setpoint')
axes[0].set_ylabel('Water Level (m)')
axes[0].legend()
axes[0].grid(True, alpha=0.3)

# Control output
for label, result in results.items():
    axes[1].plot(result['time'][:-1], result['control_output'], label=label)
axes[1].set_xlabel('Time (s)')
axes[1].set_ylabel('Control Output (m³/s)')
axes[1].legend()
axes[1].grid(True, alpha=0.3)

plt.suptitle('Controller Comparison')
plt.tight_layout()
plt.savefig('controller_comparison.png', dpi=150)
plt.show()
"""
            return code

        return f"# Unsupported plot type: {plot_type}"

    async def analyze_water_balance(self, balance_data: dict, period: str = "daily") -> dict:
        """Analyze water balance for anomaly patterns. / 水平衡异常模式分析。"""
        from mcp_servers.water_balance_server import calc_full_plant_balance, detect_balance_anomaly
        import asyncio

        nodes_data = balance_data.get("nodes_data", [])
        edges_data = balance_data.get("edges_data", [])

        if nodes_data and edges_data:
            balance = await asyncio.to_thread(calc_full_plant_balance, nodes_data=nodes_data, edges_data=edges_data)
        else:
            balance = balance_data

        residuals = balance.get("node_residuals", {})
        anomalies = await asyncio.to_thread(detect_balance_anomaly, residuals=residuals)

        return {
            "balance": balance,
            "anomalies": anomalies,
            "period": period,
            "total_intake": balance.get("total_intake", 0),
            "reuse_rate": balance.get("reuse_rate", 0),
            "n_anomalies": len(anomalies.get("anomalies", [])),
        }

    async def analyze_evaporation_trend(self, historical_evap: list[dict], weather_history: list[dict]) -> dict:
        """Analyze evaporation trends and correlations. / 蒸发趋势与相关性分析。"""
        evap_values = [e.get("evap_rate_m3h", e.get("value", 0)) for e in historical_evap]
        temp_values = [w.get("t_db", w.get("temperature", 25)) for w in weather_history]

        n = min(len(evap_values), len(temp_values))
        if n == 0:
            return {"trend": "insufficient_data", "correlation": 0, "n_samples": 0}

        evap_values = evap_values[:n]
        temp_values = temp_values[:n]
        avg_evap = sum(evap_values) / n
        avg_temp = sum(temp_values) / n

        # Simple correlation coefficient
        cov = sum((e - avg_evap) * (t - avg_temp) for e, t in zip(evap_values, temp_values)) / n
        std_e = (sum((e - avg_evap)**2 for e in evap_values) / n) ** 0.5
        std_t = (sum((t - avg_temp)**2 for t in temp_values) / n) ** 0.5
        correlation = cov / (std_e * std_t) if std_e > 0 and std_t > 0 else 0

        trend = "increasing" if evap_values[-1] > evap_values[0] else "decreasing" if evap_values[-1] < evap_values[0] else "stable"

        return {
            "trend": trend,
            "correlation_temp_evap": round(correlation, 4),
            "avg_evaporation": round(avg_evap, 2),
            "avg_temperature": round(avg_temp, 2),
            "n_samples": n,
        }

    async def compare_reuse_strategies(self, strategies: list[dict]) -> dict:
        """Compare multiple reuse optimization strategies. / 对比多种回用策略。"""
        from mcp_servers.reuse_server import evaluate_reuse_benefit
        import asyncio

        results = []
        for i, strategy in enumerate(strategies):
            benefit = await asyncio.to_thread(
                evaluate_reuse_benefit,
                current_reuse_rate=strategy.get("current_rate", 0.36),
                optimized_reuse=strategy.get("optimized_reuse", {}),
                water_price=strategy.get("water_price", 4.0),
            )
            results.append({"strategy_index": i, "name": strategy.get("name", f"Strategy_{i}"), "benefit": benefit})

        results.sort(key=lambda r: r["benefit"].get("annual_cost_saving_cny", 0), reverse=True)
        for rank, r in enumerate(results):
            r["rank"] = rank + 1

        return {"strategies": results, "best": results[0]["name"] if results else None, "n_strategies": len(strategies)}
