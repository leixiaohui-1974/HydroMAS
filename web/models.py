"""Pydantic request/response models for the web API.
Web API 的 Pydantic 请求/响应模型。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

_MAX_SIMULATION_STEPS = 100_000


# ---------- Simulation / 仿真 ----------

class SimulationRequest(BaseModel):
    duration: float = Field(300, gt=0, le=86400, description="仿真时长 (s)")
    dt: float = Field(1.0, gt=0, le=60, description="时间步长 (s)")
    initial_h: float = Field(0.5, ge=0, le=100, description="初始水位 (m)")
    q_in_profile: list[list[float]] = Field(
        default=[[0, 0.01]],
        max_length=1000,
        description="入流量分段 [[t, q_in], ...]",
    )
    tank_params: dict | None = Field(None, max_length=20, description="水箱参数")
    solver: Literal["euler", "rk4"] = Field("rk4", description="求解器")

    @model_validator(mode="after")
    def check_step_count(self):
        if self.duration / self.dt > _MAX_SIMULATION_STEPS:
            raise ValueError(
                f"Too many simulation steps: duration/dt = {self.duration / self.dt:.0f} "
                f"exceeds limit {_MAX_SIMULATION_STEPS}"
            )
        return self


# ---------- Control / 控制 ----------

class ControlRequest(BaseModel):
    setpoint: float = Field(1.0, ge=0, le=100, description="目标水位 (m)")
    controller_type: Literal["PID", "MPC"] = Field("PID", description="控制器类型")
    duration: float = Field(300, gt=0, le=86400, description="仿真时长 (s)")
    dt: float = Field(1.0, gt=0, le=60, description="时间步长 (s)")
    initial_h: float = Field(0.5, ge=0, le=100, description="初始水位 (m)")
    params: dict | None = Field(None, max_length=20, description="控制器参数")
    tank_params: dict | None = Field(None, max_length=20, description="水箱参数")

    @model_validator(mode="after")
    def check_step_count(self):
        if self.duration / self.dt > _MAX_SIMULATION_STEPS:
            raise ValueError(
                f"Too many simulation steps: duration/dt = {self.duration / self.dt:.0f} "
                f"exceeds limit {_MAX_SIMULATION_STEPS}"
            )
        return self


# ---------- Prediction / 预测 ----------

class PredictionRequest(BaseModel):
    historical_data: list[float] = Field(..., min_length=2, max_length=100000, description="历史时序数据")
    horizon: int = Field(60, gt=0, le=10000, description="预测步数")
    model: Literal["linear", "polynomial"] = Field("linear", description="预测模型")
    lookback: int | None = Field(None, gt=0, description="回看窗口")
    degree: int = Field(2, ge=1, le=10, description="多项式阶数")


# ---------- Scheduling / 调度 ----------

class SchedulingRequest(BaseModel):
    demand_forecast: list[float] = Field(..., min_length=1, max_length=100000, description="需求预测序列")
    supply_capacity: float | None = Field(None, gt=0, le=1e6, description="供水能力上限")
    method: Literal["lp", "rule"] = Field("lp", description="优化方法")
    constraints: dict | None = Field(None, max_length=20, description="附加约束 {min_level, max_level, ...}")
    objective: Literal["minimize_cost", "maximize_supply"] = Field("minimize_cost", description="优化目标")


# ---------- Evaluation / 评价 ----------

class EvaluationRequest(BaseModel):
    observed: list[float] = Field(..., min_length=1, max_length=100000, description="观测值")
    predicted: list[float] = Field(..., min_length=1, max_length=100000, description="预测/响应值")
    metrics: list[str] = Field(
        default=["RMSE", "MAE", "NSE"],
        max_length=20,
        description="评价指标列表",
    )
    time_series: list[float] | None = Field(None, max_length=100000, description="时间序列")
    setpoint: float | None = Field(None, ge=-1000, le=1000, description="控制目标值")

    @model_validator(mode="after")
    def check_length_match(self):
        if len(self.observed) != len(self.predicted):
            raise ValueError(
                f"observed and predicted must have same length, "
                f"got {len(self.observed)} and {len(self.predicted)}"
            )
        return self


class WNALRequest(BaseModel):
    capabilities: dict[str, float] = Field(..., max_length=20, description="各能力项得分 (0-100)")


# ---------- ODD / 安全 ----------

class ODDCheckRequest(BaseModel):
    state: dict[str, float] = Field(..., max_length=50, description="当前系统状态")
    odd_config: dict | None = Field(None, max_length=100, description="自定义 ODD 配置")


class ODDSeriesRequest(BaseModel):
    states: list[dict[str, float]] = Field(..., min_length=1, max_length=10000, description="状态序列")
    times: list[float] | None = Field(None, max_length=10000, description="时间戳序列")
    odd_config: dict | None = Field(None, max_length=100, description="自定义 ODD 配置")

    @model_validator(mode="after")
    def check_times_length(self):
        if self.times is not None and len(self.times) != len(self.states):
            raise ValueError(
                f"times length ({len(self.times)}) must match states length ({len(self.states)})"
            )
        return self


# ---------- Design / 设计 ----------

class SensitivityRequest(BaseModel):
    base_params: dict[str, float] = Field(..., max_length=20, description="基准参数")
    param_ranges: dict[str, list[float]] = Field(
        ..., max_length=20, description="参数范围 {name: [min, max]}"
    )
    method: Literal["OAT", "Morris"] = Field("OAT", description="分析方法")
    n_levels: int = Field(10, ge=2, le=1000, description="水平数")

    @model_validator(mode="after")
    def check_total_evaluations(self):
        total = self.n_levels * len(self.param_ranges)
        if total > 5000:
            raise ValueError(
                f"Too many evaluations: {self.n_levels} x {len(self.param_ranges)} = {total} "
                f"exceeds limit 5000"
            )
        return self


class SizingRequest(BaseModel):
    demand_peak: float = Field(0.03, gt=0, le=1e6, description="峰值需求 (m³/s)")
    duration_hours: float = Field(4.0, gt=0, le=720, description="持续时间 (h)")
    safety_factor: float = Field(1.2, ge=1.0, le=5.0, description="安全系数")


# ---------- DataClean / 数据清洗 ----------

class OutlierDetectRequest(BaseModel):
    data: list[float] = Field(..., min_length=3, max_length=100000, description="输入数据")
    method: Literal["3sigma", "iqr", "mad"] = Field("3sigma", description="检测方法")
    threshold: float = Field(3.0, gt=0, le=100, description="阈值")


class InterpolateRequest(BaseModel):
    data: list[float | None] = Field(..., min_length=2, max_length=100000, description="含缺失值的数据")
    method: Literal["linear", "spline", "median"] = Field("linear", description="插值方法")


# ---------- Identification / 辨识 ----------

class IdentificationRequest(BaseModel):
    observed_h: list[float] = Field(..., min_length=3, max_length=100000, description="观测水位")
    observed_q_out: list[float] = Field(..., min_length=3, max_length=100000, description="观测出流量")
    model_type: Literal["nonlinear", "ARX"] = Field("nonlinear", description="模型类型")
    initial_guess: dict | None = Field(None, max_length=20, description="初始猜测")

    @model_validator(mode="after")
    def check_length_match(self):
        if len(self.observed_h) != len(self.observed_q_out):
            raise ValueError(
                f"observed_h and observed_q_out must have same length, "
                f"got {len(self.observed_h)} and {len(self.observed_q_out)}"
            )
        return self


class ARXRequest(BaseModel):
    y: list[float] = Field(..., min_length=4, max_length=100000, description="输出时序")
    u: list[float] = Field(..., min_length=4, max_length=100000, description="输入时序")
    na: int = Field(2, ge=1, le=100, description="自回归阶数")
    nb: int = Field(2, ge=1, le=100, description="外源输入阶数")

    @model_validator(mode="after")
    def check_length_match(self):
        if len(self.y) != len(self.u):
            raise ValueError(
                f"y and u must have same length, got {len(self.y)} and {len(self.u)}"
            )
        return self


# ---------- Skills / 技能 ----------

class SkillRequest(BaseModel):
    skill_name: str = Field(..., min_length=1, max_length=200, description="技能名称")
    params: dict = Field(default_factory=dict, max_length=50, description="技能参数")


class FourPredRequest(BaseModel):
    water_level_data: list[float] = Field(..., min_length=2, max_length=100000, description="水位数据")
    inflow_data: list[float] | None = Field(None, max_length=100000, description="入流量数据")
    risk_threshold: float = Field(0.7, ge=0.0, le=1.0, description="风险阈值")


# ---------- Assistant / 助手 ----------

class AssistantMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000, description="用户消息")
    role: Literal["operator", "engineer", "analyst", "admin"] = Field("admin", description="用户角色")
    params: dict = Field(default_factory=dict, max_length=50, description="附加参数")
    history: list[dict] = Field(default_factory=list, max_length=100, description="对话历史")


# ---------- Water Balance / 水平衡 ----------

class WaterBalanceRequest(BaseModel):
    nodes_data: list[dict] = Field(..., min_length=1, max_length=100, description="水平衡节点数据")
    edges_data: list[list[str]] = Field(..., min_length=1, max_length=200, description="水平衡边数据")


class LeakDetectionRequest(BaseModel):
    graph_nodes: list[dict] = Field(..., min_length=2, max_length=500, description="管网节点")
    graph_edges: list[dict] = Field(..., min_length=1, max_length=1000, description="管网边")
    threshold: float = Field(0.95, ge=0.0, le=1.0, description="检测阈值")


class EvaporationRequest(BaseModel):
    tower_params: dict = Field(..., description="冷却塔参数")
    weather: dict = Field(..., description="气象数据")


class ReuseRequest(BaseModel):
    source_quality: dict = Field(..., description="回用水源水质")
    target_requirements: list[dict] = Field(..., min_length=1, description="目标车间需求")


class GlobalDispatchRequest(BaseModel):
    demand_forecast: dict = Field(..., description="需求预测")
    supply_config: dict = Field(..., description="供水配置")
    reuse_config: dict | None = Field(None, description="回用配置")
    method: Literal["lp", "rl"] = Field("lp", description="优化方法")


class DailyReportRequest(BaseModel):
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="报告日期")
    include_sections: list[str] = Field(
        default=["balance", "anomaly", "kpi", "evaporation", "reuse"],
        description="包含章节"
    )
