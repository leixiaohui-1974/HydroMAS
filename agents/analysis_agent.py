"""Analysis Agent — flexible data analysis and script generation.
分析 Agent — 灵活数据分析和脚本生成。

This agent represents the "flexible" layer of the architecture:
it can dynamically compose analysis workflows, generate comparison
scripts, and produce visualizations.
"""

from __future__ import annotations

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
        from mcp_servers.evaluation_server import evaluate_performance

        if metrics is None:
            metrics = ["RMSE", "MAE"]
        if weights is None:
            weights = {m: 1.0 / len(metrics) for m in metrics}

        results = []
        for i, scheme in enumerate(schemes):
            sim = simulate_tank(**scheme)
            results.append({
                "scheme_index": i,
                "scheme": scheme,
                "simulation": sim,
                "max_level": max(sim["water_level"]),
                "min_level": min(sim["water_level"]),
                "final_level": sim["water_level"][-1],
            })

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
