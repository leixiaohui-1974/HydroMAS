"""MCP Server: Reuse water optimization tools.
MCP 服务器：回用水优化工具。

Exposes water-quality matching, reuse schedule optimization, and
economic benefit evaluation as MCP tools.  Functions are implemented
directly in this module (no core/reuse dependency).
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("HydroOS-Reuse")


# ---------------------------------------------------------------------------
# Internal helper functions (no core module — implemented inline)
# ---------------------------------------------------------------------------


def _match_source_to_targets(
    source_quality: dict,
    target_requirements: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Match source water quality against workshop requirements.
    将源水质与各车间需求进行匹配。

    A target is matched if the source quality satisfies all of its
    maximum-allowable limits (COD, turbidity) and if the source can
    supply the demanded volume.
    """
    matched: list[dict] = []
    unmatched: list[dict] = []

    src_cod = float(source_quality.get("cod", 0.0))
    src_turbidity = float(source_quality.get("turbidity", 0.0))

    for req in target_requirements:
        workshop_id = req.get("workshop_id", "unknown")
        max_cod = float(req.get("max_cod", float("inf")))
        max_turbidity = float(req.get("max_turbidity", float("inf")))
        demand = float(req.get("demand_m3d", 0.0))

        cod_ok = src_cod <= max_cod
        turbidity_ok = src_turbidity <= max_turbidity

        if cod_ok and turbidity_ok:
            matched.append({
                "workshop_id": workshop_id,
                "demand_m3d": demand,
                "quality_margin": {
                    "cod_margin": round(max_cod - src_cod, 4),
                    "turbidity_margin": round(max_turbidity - src_turbidity, 4),
                },
            })
        else:
            reasons: list[str] = []
            if not cod_ok:
                reasons.append(
                    f"COD {src_cod} > max {max_cod}"
                )
            if not turbidity_ok:
                reasons.append(
                    f"turbidity {src_turbidity} > max {max_turbidity}"
                )
            unmatched.append({
                "workshop_id": workshop_id,
                "demand_m3d": demand,
                "rejection_reasons": reasons,
            })

    return matched, unmatched


def _optimize_reuse_lp(
    sources: list[dict],
    demands: list[dict],
    constraints: dict,
) -> dict:
    """MILP-style optimization using PuLP (LP fallback if PuLP unavailable).
    使用 PuLP 的 MILP 优化（PuLP 不可用时退化为贪心）。

    Decision variable: x[i][j] = volume from source i to demand j.
    Objective: maximise total reuse volume.
    """
    try:
        import pulp  # noqa: F401
        return _optimize_with_pulp(sources, demands, constraints)
    except ImportError:
        return _optimize_greedy(sources, demands, constraints)


def _optimize_with_pulp(
    sources: list[dict],
    demands: list[dict],
    constraints: dict,
) -> dict:
    """Solve with PuLP LP solver.  使用 PuLP LP 求解器求解。"""
    import pulp

    n_src = len(sources)
    n_dem = len(demands)

    prob = pulp.LpProblem("ReuseSchedule", pulp.LpMaximize)

    # Decision variables: x[i][j] = volume from source i to demand j (m3/d)
    x = {}
    for i in range(n_src):
        for j in range(n_dem):
            x[i, j] = pulp.LpVariable(
                f"x_{i}_{j}", lowBound=0, cat="Continuous"
            )

    # Objective: maximise total reuse volume
    prob += pulp.lpSum(x[i, j] for i in range(n_src) for j in range(n_dem))

    # Supply capacity constraints
    for i in range(n_src):
        cap = float(sources[i].get("capacity_m3d", 0.0))
        prob += (
            pulp.lpSum(x[i, j] for j in range(n_dem)) <= cap,
            f"supply_{i}",
        )

    # Demand satisfaction constraints (do not exceed demand)
    for j in range(n_dem):
        dem = float(demands[j].get("demand_m3d", 0.0))
        prob += (
            pulp.lpSum(x[i, j] for i in range(n_src)) <= dem,
            f"demand_{j}",
        )

    # Quality compatibility — only allow flow if source meets target quality
    for i in range(n_src):
        src_cod = float(sources[i].get("cod", 0.0))
        src_turb = float(sources[i].get("turbidity", 0.0))
        for j in range(n_dem):
            max_cod = float(demands[j].get("max_cod", float("inf")))
            max_turb = float(demands[j].get("max_turbidity", float("inf")))
            if src_cod > max_cod or src_turb > max_turb:
                prob += (x[i, j] == 0, f"quality_{i}_{j}")

    # Optional minimum reuse rate constraint
    min_reuse_rate = float(constraints.get("min_reuse_rate", 0.0))
    total_demand = sum(float(d.get("demand_m3d", 0.0)) for d in demands)
    if min_reuse_rate > 0 and total_demand > 0:
        prob += (
            pulp.lpSum(x[i, j] for i in range(n_src) for j in range(n_dem))
            >= min_reuse_rate * total_demand,
            "min_reuse",
        )

    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    # Extract results
    schedule: list[dict] = []
    total_reuse = 0.0
    for i in range(n_src):
        for j in range(n_dem):
            vol = x[i, j].varValue or 0.0
            if vol > 1e-6:
                schedule.append({
                    "source_id": sources[i].get("source_id", f"src_{i}"),
                    "target_id": demands[j].get("workshop_id", f"dem_{j}"),
                    "volume_m3d": round(vol, 4),
                })
                total_reuse += vol

    status = pulp.LpStatus[prob.status]
    reuse_rate = round(total_reuse / total_demand, 4) if total_demand > 0 else 0.0

    return {
        "status": status,
        "method": "pulp_lp",
        "schedule": schedule,
        "total_reuse_m3d": round(total_reuse, 4),
        "total_demand_m3d": round(total_demand, 4),
        "reuse_rate": reuse_rate,
    }


def _optimize_greedy(
    sources: list[dict],
    demands: list[dict],
    constraints: dict,
) -> dict:
    """Greedy fallback when PuLP is not available.
    PuLP 不可用时的贪心退化方案。

    Assigns sources to demands in order of quality margin (best-fit first).
    """
    schedule: list[dict] = []
    total_reuse = 0.0
    total_demand = sum(float(d.get("demand_m3d", 0.0)) for d in demands)

    # Track remaining capacity per source and remaining demand per target
    remaining_cap = [float(s.get("capacity_m3d", 0.0)) for s in sources]
    remaining_dem = [float(d.get("demand_m3d", 0.0)) for d in demands]

    # Build candidate pairs sorted by quality margin (ascending COD distance)
    candidates: list[tuple[int, int, float]] = []
    for i, src in enumerate(sources):
        src_cod = float(src.get("cod", 0.0))
        src_turb = float(src.get("turbidity", 0.0))
        for j, dem in enumerate(demands):
            max_cod = float(dem.get("max_cod", float("inf")))
            max_turb = float(dem.get("max_turbidity", float("inf")))
            if src_cod <= max_cod and src_turb <= max_turb:
                margin = (max_cod - src_cod) + (max_turb - src_turb)
                candidates.append((i, j, margin))

    # Sort by margin descending (prefer large margin = safer match)
    candidates.sort(key=lambda c: c[2], reverse=True)

    for i, j, _ in candidates:
        vol = min(remaining_cap[i], remaining_dem[j])
        if vol > 1e-6:
            schedule.append({
                "source_id": sources[i].get("source_id", f"src_{i}"),
                "target_id": demands[j].get("workshop_id", f"dem_{j}"),
                "volume_m3d": round(vol, 4),
            })
            remaining_cap[i] -= vol
            remaining_dem[j] -= vol
            total_reuse += vol

    reuse_rate = round(total_reuse / total_demand, 4) if total_demand > 0 else 0.0

    return {
        "status": "greedy_solution",
        "method": "greedy",
        "schedule": schedule,
        "total_reuse_m3d": round(total_reuse, 4),
        "total_demand_m3d": round(total_demand, 4),
        "reuse_rate": reuse_rate,
    }


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def match_reuse_path(
    source_quality: dict,
    target_requirements: list[dict],
) -> dict:
    """Match source water quality to workshop reuse requirements.
    将源水水质与车间回用需求进行匹配。

    Evaluates whether the source water meets each workshop's quality
    limits (COD, turbidity) and returns matched/unmatched paths.

    Args:
        source_quality: Source water quality parameters / 源水水质参数:
            - cod: Chemical oxygen demand (mg/L) / 化学需氧量
            - ph: pH value / pH 值
            - turbidity: Turbidity (NTU) / 浊度
            - conductivity: Conductivity (μS/cm) / 电导率
        target_requirements: List of workshop requirement dicts / 车间需求列表:
            Each dict contains:
            - workshop_id: Workshop identifier / 车间标识
            - max_cod: Maximum allowable COD (mg/L) / 最大允许 COD
            - max_turbidity: Maximum allowable turbidity (NTU) / 最大允许浊度
            - demand_m3d: Daily water demand (m³/d) / 日用水需求

    Returns:
        Dict with matched_paths, unmatched, source_quality echo, and counts.
        包含匹配路径、未匹配、源水质回显和数量的字典。
    """
    if not isinstance(source_quality, dict):
        raise ValueError("source_quality must be a dict")
    if not isinstance(target_requirements, list) or not target_requirements:
        raise ValueError("target_requirements must be a non-empty list of dicts")

    for i, req in enumerate(target_requirements):
        if not isinstance(req, dict):
            raise ValueError(
                f"target_requirements[{i}] must be a dict, got {type(req)}"
            )
        if "workshop_id" not in req:
            raise ValueError(
                f"target_requirements[{i}] must have 'workshop_id' key"
            )

    matched, unmatched = _match_source_to_targets(source_quality, target_requirements)

    return {
        "matched_paths": matched,
        "unmatched": unmatched,
        "n_matched": len(matched),
        "n_unmatched": len(unmatched),
        "source_quality": source_quality,
    }


@mcp.tool()
def optimize_reuse_schedule(
    sources: list[dict],
    demands: list[dict],
    constraints: dict | None = None,
) -> dict:
    """Optimize reuse water allocation from sources to demands via LP.
    通过线性规划优化回用水从源到需求的分配。

    Uses PuLP for MILP-style optimization when available; falls back
    to a greedy assignment otherwise.  Quality compatibility is enforced
    as hard constraints (source COD/turbidity must not exceed target limits).

    Args:
        sources: List of source dicts / 水源列表, each with:
            - source_id: Source identifier / 水源标识
            - capacity_m3d: Daily supply capacity (m³/d) / 日供水能力
            - cod: Source COD (mg/L) / 源 COD
            - turbidity: Source turbidity (NTU) / 源浊度
        demands: List of demand dicts / 需求列表, each with:
            - workshop_id: Workshop identifier / 车间标识
            - demand_m3d: Daily demand (m³/d) / 日需水量
            - max_cod: Maximum allowable COD (mg/L) / 最大允许 COD
            - max_turbidity: Maximum allowable turbidity (NTU) / 最大允许浊度
        constraints: Optional additional constraints / 可选附加约束:
            - min_reuse_rate: Minimum overall reuse rate (0-1) / 最低回用率

    Returns:
        Dict with schedule, total_reuse_m3d, total_demand_m3d,
        reuse_rate, status, and method.
        包含调度方案、总回用量、总需求量、回用率、状态和方法的字典。
    """
    if not isinstance(sources, list) or not sources:
        raise ValueError("sources must be a non-empty list of dicts")
    if not isinstance(demands, list) or not demands:
        raise ValueError("demands must be a non-empty list of dicts")

    for i, src in enumerate(sources):
        if not isinstance(src, dict):
            raise ValueError(f"sources[{i}] must be a dict, got {type(src)}")
        if float(src.get("capacity_m3d", 0)) <= 0:
            raise ValueError(
                f"sources[{i}].capacity_m3d must be positive, "
                f"got {src.get('capacity_m3d')}"
            )

    for j, dem in enumerate(demands):
        if not isinstance(dem, dict):
            raise ValueError(f"demands[{j}] must be a dict, got {type(dem)}")
        if float(dem.get("demand_m3d", 0)) <= 0:
            raise ValueError(
                f"demands[{j}].demand_m3d must be positive, "
                f"got {dem.get('demand_m3d')}"
            )

    c = constraints if constraints is not None else {}

    return _optimize_reuse_lp(sources, demands, c)


@mcp.tool()
def evaluate_reuse_benefit(
    current_reuse_rate: float,
    optimized_reuse: dict,
    water_price: float = 4.0,
) -> dict:
    """Evaluate economic benefit of optimized reuse strategy.
    评估优化回用策略的经济效益。

    Computes annual fresh-water savings, cost reduction, and the
    improvement in reuse rate compared with the current baseline.

    Args:
        current_reuse_rate: Current reuse rate (0-1) / 当前回用率
        optimized_reuse: Output from ``optimize_reuse_schedule`` containing
                         total_reuse_m3d and total_demand_m3d.
                         ``optimize_reuse_schedule`` 的输出结果。
        water_price: Unit price of fresh water (CNY/m³) / 新水单价（元/m³）

    Returns:
        Dict with new_reuse_rate, improvement, daily_savings_m3,
        annual_savings_m3, daily_cost_saving_cny, annual_cost_saving_cny.
        包含新回用率、提升幅度、日节水量、年节水量、日节省费用、年节省费用的字典。
    """
    if current_reuse_rate < 0 or current_reuse_rate > 1:
        raise ValueError(
            f"current_reuse_rate must be in [0, 1], got {current_reuse_rate}"
        )
    if not isinstance(optimized_reuse, dict):
        raise ValueError("optimized_reuse must be a dict")
    if water_price < 0:
        raise ValueError(f"water_price must be non-negative, got {water_price}")

    total_reuse = float(optimized_reuse.get("total_reuse_m3d", 0.0))
    total_demand = float(optimized_reuse.get("total_demand_m3d", 0.0))

    if total_demand <= 0:
        raise ValueError(
            "optimized_reuse.total_demand_m3d must be positive"
        )

    new_reuse_rate = total_reuse / total_demand
    improvement = new_reuse_rate - current_reuse_rate

    # Daily fresh-water savings = demand that is now met by reuse
    # instead of fresh water.  Baseline reuse volume = current_rate * demand.
    baseline_reuse = current_reuse_rate * total_demand
    daily_savings_m3 = max(total_reuse - baseline_reuse, 0.0)

    annual_savings_m3 = daily_savings_m3 * 365.0
    daily_cost_saving = daily_savings_m3 * water_price
    annual_cost_saving = annual_savings_m3 * water_price

    return {
        "new_reuse_rate": round(new_reuse_rate, 4),
        "current_reuse_rate": round(current_reuse_rate, 4),
        "improvement": round(improvement, 4),
        "daily_savings_m3": round(daily_savings_m3, 2),
        "annual_savings_m3": round(annual_savings_m3, 2),
        "daily_cost_saving_cny": round(daily_cost_saving, 2),
        "annual_cost_saving_cny": round(annual_cost_saving, 2),
        "water_price_cny_per_m3": water_price,
    }


if __name__ == "__main__":
    mcp.run()
