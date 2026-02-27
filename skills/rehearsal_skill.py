"""Skill: Rehearsal — multi-scheme parallel simulation (四预第三环: 预演).
技能：预演 — 多方案并行仿真推演。

Simulates N schemes in parallel, evaluates each, and ranks them.

Part of: 预报(Forecast) → 预警(Warning) → 预演(Rehearsal) → 预案(Plan)

MVP: Compare 3 inflow adjustment schemes for a single tank.
Extension: 3D flood visualization, multi-reservoir coordination.
"""

from __future__ import annotations

from skills.base_skill import BaseSkill, SkillResult


class RehearsalSkill(BaseSkill):
    """Rehearsal Skill — parallel scenario simulation and comparison.
    预演 Skill — 并行方案仿真与对比。

    Steps:
        1. Batch-simulate all schemes (parallel via Ray when available)
        2. Evaluate each scheme's performance
        3. Multi-criteria ranking
    """

    async def execute(self, params: dict) -> SkillResult:
        steps = []
        duration = params.get("duration", 600)
        weights = params.get("weights", {"safety": 0.4, "efficiency": 0.3, "cost": 0.3})

        schemes = params.get("schemes")
        if not schemes:
            # Default: 3 scenarios — low/medium/high inflow
            schemes = [
                {
                    "q_in_profile": [[0, 0.01], [duration, 0.01]],
                    "initial_h": 0.5,
                    "label": "Low inflow (0.01 m³/s)",
                },
                {
                    "q_in_profile": [[0, 0.025], [duration, 0.025]],
                    "initial_h": 0.5,
                    "label": "Medium inflow (0.025 m³/s)",
                },
                {
                    "q_in_profile": [[0, 0.04], [duration, 0.04]],
                    "initial_h": 0.5,
                    "label": "High inflow (0.04 m³/s)",
                },
            ]

        # Step 1: Simulate all schemes
        sim_results = []
        for scheme in schemes:
            profile = scheme.get("q_in_profile", [[0, 0.01]])
            sim = await self.call_tool("simulate_tank", {
                "duration": duration,
                "dt": scheme.get("dt", 1.0),
                "q_in_profile": profile,
                "initial_h": scheme.get("initial_h", 0.5),
                "tank_params": scheme.get("tank_params"),
            })
            sim_results.append(sim)
        steps.append("batch_simulation")

        # Step 2: Evaluate each scheme
        evaluations = []
        for sim in sim_results:
            levels = sim.get("water_level", [])
            if not levels:
                evaluations.append({
                    "max_level": 0.0, "min_level": 0.0, "final_level": 0.0,
                    "level_range": 0.0, "odd_zone": "unknown", "odd_violations": 0,
                })
                continue
            max_lev = max(levels)
            min_lev = min(levels)
            # Check for ODD violations
            odd_check = await self.call_tool("check_odd", {
                "current_state": {"water_level": max_lev},
            })
            n_violations = 1 if odd_check.get("zone") == "mrc" else 0

            eval_item = {
                "max_level": max_lev,
                "min_level": min_lev,
                "final_level": levels[-1],
                "level_range": max_lev - min_lev,
                "odd_zone": odd_check.get("zone", "unknown"),
                "odd_violations": n_violations,
            }
            evaluations.append(eval_item)
        steps.append("scheme_evaluation")

        # Step 3: Rank schemes using weighted scoring
        ranking = self._rank_schemes(schemes, evaluations, weights)
        steps.append("ranking")

        return SkillResult(
            success=True,
            data={
                "ranking": ranking,
                "sim_results": sim_results,
                "evaluations": evaluations,
                "schemes": schemes,
                "weights": weights,
            },
            steps_completed=steps,
        )

    @staticmethod
    def _rank_schemes(
        schemes: list[dict],
        evaluations: list[dict],
        weights: dict,
    ) -> list[dict]:
        """Rank schemes by weighted multi-criteria score.
        基于加权多准则分数排列方案。

        Scoring:
            - safety: penalize ODD violations and extreme levels
            - efficiency: reward stable final level near target (1.0m)
            - cost: reward lower total inflow (lower level_range proxy)
        """
        scores = []
        for i, ev in enumerate(evaluations):
            # Safety score: 0 if MRC violation, proportional to distance from bounds
            safety_score = 0.0 if ev["odd_violations"] > 0 else 1.0
            if ev["max_level"] > 1.5:
                safety_score *= max(0, 1 - (ev["max_level"] - 1.5) / 0.5)
            if ev["min_level"] < 0.2:
                safety_score *= max(0, ev["min_level"] / 0.2)

            # Efficiency: how close final level is to target
            from core.config import load_tank_config
            target = load_tank_config().get("target_level", 1.0)
            efficiency_score = max(0, 1 - abs(ev["final_level"] - target) / target)

            # Cost proxy: lower range = more stable = less energy
            max_range = 2.0
            cost_score = max(0, 1 - ev["level_range"] / max_range)

            total = (
                weights.get("safety", 0.4) * safety_score
                + weights.get("efficiency", 0.3) * efficiency_score
                + weights.get("cost", 0.3) * cost_score
            )

            label = schemes[i].get("label", f"Scheme {i+1}")
            scores.append({
                "rank": 0,  # filled below
                "scheme_index": i,
                "label": label,
                "total_score": round(total, 4),
                "safety_score": round(safety_score, 4),
                "efficiency_score": round(efficiency_score, 4),
                "cost_score": round(cost_score, 4),
            })

        # Sort by total score descending
        scores.sort(key=lambda s: s["total_score"], reverse=True)
        for rank, s in enumerate(scores):
            s["rank"] = rank + 1

        return scores
