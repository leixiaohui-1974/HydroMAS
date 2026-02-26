"""Skill: Emergency Plan — generate executable dispatch plan (四预第四环: 预案).
技能：预案 — 生成可执行调度方案。

Generates an emergency response plan aligned with Ministry of Water Resources
requirements: dispatch command sequence, safety verification, responsibility matrix.

Part of: 预报(Forecast) → 预警(Warning) → 预演(Rehearsal) → 预案(Plan)

MVP: Generate inflow adjustment schedule + ODD safety verification.
Extension: Non-engineering measures, responsibility assignment, reporting workflow.
"""

from __future__ import annotations

from skills.base_skill import BaseSkill, SkillResult


class PlanSkill(BaseSkill):
    """Emergency Plan Skill — generate dispatch plan from rehearsal results.
    预案 Skill — 从预演结果生成调度方案。

    Steps:
        1. Get best scheme from rehearsal (or run rehearsal)
        2. Optimize dispatch schedule for the best scheme
        3. ODD safety verification of the planned actions
        4. Generate plan document
    """

    async def execute(self, params: dict) -> SkillResult:
        steps = []
        constraints = params.get("constraints", {})

        # Step 1: Get rehearsal results
        rehearsal = params.get("rehearsal")
        if not rehearsal:
            # Need to run rehearsal inline
            schemes = params.get("schemes")
            if not schemes:
                schemes = [
                    {"q_in_profile": [[0, 0.01], [600, 0.01]], "initial_h": 0.5,
                     "label": "Conservative"},
                    {"q_in_profile": [[0, 0.025], [600, 0.025]], "initial_h": 0.5,
                     "label": "Moderate"},
                    {"q_in_profile": [[0, 0.04], [600, 0.04]], "initial_h": 0.5,
                     "label": "Aggressive"},
                ]
            # Simulate each scheme inline
            sim_results = []
            for s in schemes:
                sim = await self.call_tool("simulate_tank", {
                    "duration": params.get("duration", 600),
                    "q_in_profile": s.get("q_in_profile"),
                    "initial_h": s.get("initial_h", 0.5),
                })
                sim_results.append(sim)
            # Pick the scheme with best final level near target
            target = constraints.get("target_level", 1.0)
            best_idx = min(
                range(len(sim_results)),
                key=lambda i: abs(sim_results[i]["water_level"][-1] - target),
            )
            rehearsal = {
                "ranking": [{"scheme_index": best_idx, "label": schemes[best_idx].get("label", "")}],
                "sim_results": sim_results,
                "schemes": schemes,
            }
            steps.append("inline_rehearsal")

        best_scheme = rehearsal["ranking"][0]
        best_idx = best_scheme.get("scheme_index", 0)
        steps.append("best_scheme_selection")

        # Step 2: Optimize dispatch schedule
        # Use demand from simulation outflow as demand forecast
        best_sim = rehearsal["sim_results"][best_idx]
        demand = best_sim.get("outflow", [0.01] * 10)
        # Sample demand at intervals
        n_periods = min(10, len(demand))
        step_size = max(1, len(demand) // n_periods)
        sampled_demand = [demand[i * step_size] for i in range(n_periods)]

        schedule = await self.call_tool("optimize_schedule", {
            "demand_forecast": sampled_demand,
            "supply_capacity": constraints.get("supply_capacity", 0.05),
            "constraints": constraints,
            "method": "rule",
        })
        steps.append("schedule_optimization")

        # Step 3: ODD safety verification
        safety_check = await self.call_tool("check_odd", {
            "current_state": {"water_level": best_sim["water_level"][-1]},
        })
        steps.append("safety_verification")

        # Step 4: Generate plan document
        plan_doc = self._generate_plan_document(
            best_scheme, schedule, safety_check, constraints
        )
        steps.append("plan_document_generation")

        return SkillResult(
            success=True,
            data={
                "plan": plan_doc,
                "schedule": schedule,
                "safety_check": safety_check,
                "best_scheme": best_scheme,
            },
            steps_completed=steps,
        )

    @staticmethod
    def _generate_plan_document(
        best_scheme: dict,
        schedule: dict,
        safety_check: dict,
        constraints: dict,
    ) -> dict:
        """Generate structured plan document.
        生成结构化预案文档。
        """
        return {
            "title": "Emergency Dispatch Plan / 应急调度预案",
            "selected_scheme": best_scheme.get("label", "Best scheme"),
            "dispatch_commands": {
                "inflow_rate": schedule.get("inflow_rate", schedule.get("schedule", [])),
                "rule_applied": schedule.get("rule", "optimized"),
                "priority": schedule.get("priority", "normal"),
            },
            "safety_verification": {
                "odd_zone": safety_check.get("zone", "unknown"),
                "violations": safety_check.get("n_violations", 0),
                "approved": safety_check.get("zone") != "mrc",
            },
            "non_engineering_measures": [
                "Issue warning notification to downstream users / 向下游用户发布预警通知",
                "Activate on-site monitoring patrol / 启动现场监测巡查",
                "Prepare emergency equipment / 准备应急物资设备",
            ],
            "reporting_flow": [
                "Operator → Dispatcher → Supervisor / 操作员→调度员→主管",
                "Update status every 30 minutes / 每30分钟更新状态",
                "Escalate if ODD violation persists > 1h / ODD越界超1小时上报",
            ],
        }
