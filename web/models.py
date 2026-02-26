"""Pydantic request/response models for the web API.
Web API 的 Pydantic 请求/响应模型。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------- Simulation / 仿真 ----------

class SimulationRequest(BaseModel):
    duration: float = Field(300, gt=0, le=86400, description="仿真时长 (s)")
    dt: float = Field(1.0, gt=0, le=60, description="时间步长 (s)")
    initial_h: float = Field(0.5, ge=0, description="初始水位 (m)")
    q_in_profile: list[list[float]] = Field(
        default=[[0, 0.01]],
        max_length=1000,
        description="入流量分段 [[t, q_in], ...]",
    )
    tank_params: dict | None = Field(None, description="水箱参数")
    solver: Literal["euler", "rk4"] = Field("euler", description="求解器")


# ---------- Control / 控制 ----------

class ControlRequest(BaseModel):
    setpoint: float = Field(1.0, ge=0, description="目标水位 (m)")
    controller_type: Literal["PID", "MPC"] = Field("PID", description="控制器类型")
    duration: float = Field(300, gt=0, le=86400, description="仿真时长 (s)")
    dt: float = Field(1.0, gt=0, le=60, description="时间步长 (s)")
    initial_h: float = Field(0.5, ge=0, description="初始水位 (m)")
    params: dict | None = Field(None, description="控制器参数")
    tank_params: dict | None = Field(None, description="水箱参数")


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
    supply_capacity: float | None = Field(None, gt=0, description="供水能力上限")
    method: Literal["lp", "rule"] = Field("lp", description="优化方法")
    constraints: dict | None = Field(None, description="附加约束 {min_level, max_level, ...}")
    objective: str = Field("minimize_cost", description="优化目标")


# ---------- Evaluation / 评价 ----------

class EvaluationRequest(BaseModel):
    observed: list[float] = Field(..., min_length=1, max_length=100000, description="观测值")
    predicted: list[float] = Field(..., min_length=1, max_length=100000, description="预测/响应值")
    metrics: list[str] = Field(
        default=["RMSE", "MAE", "NSE"],
        max_length=20,
        description="评价指标列表",
    )
    time_series: list[float] | None = Field(None, description="时间序列")
    setpoint: float | None = Field(None, description="控制目标值")


class WNALRequest(BaseModel):
    capabilities: dict[str, float] = Field(..., description="各能力项得分 (0-100)")


# ---------- ODD / 安全 ----------

class ODDCheckRequest(BaseModel):
    state: dict[str, float] = Field(..., description="当前系统状态")
    odd_config: dict | None = Field(None, description="自定义 ODD 配置")


class ODDSeriesRequest(BaseModel):
    states: list[dict[str, float]] = Field(..., min_length=1, max_length=10000, description="状态序列")
    times: list[float] | None = Field(None, description="时间戳序列")
    odd_config: dict | None = Field(None, description="自定义 ODD 配置")


# ---------- Design / 设计 ----------

class SensitivityRequest(BaseModel):
    base_params: dict[str, float] = Field(..., description="基准参数")
    param_ranges: dict[str, list[float]] = Field(
        ..., description="参数范围 {name: [min, max]}"
    )
    method: Literal["OAT", "Morris"] = Field("OAT", description="分析方法")
    n_levels: int = Field(10, ge=2, le=1000, description="水平数")


class SizingRequest(BaseModel):
    demand_peak: float = Field(0.03, gt=0, description="峰值需求 (m³/s)")
    duration_hours: float = Field(4.0, gt=0, le=720, description="持续时间 (h)")
    safety_factor: float = Field(1.2, ge=1.0, le=5.0, description="安全系数")


# ---------- DataClean / 数据清洗 ----------

class OutlierDetectRequest(BaseModel):
    data: list[float] = Field(..., min_length=3, max_length=100000, description="输入数据")
    method: Literal["3sigma", "iqr", "mad"] = Field("3sigma", description="检测方法")
    threshold: float = Field(3.0, gt=0, description="阈值")


class InterpolateRequest(BaseModel):
    data: list[float | None] = Field(..., min_length=2, max_length=100000, description="含缺失值的数据")
    method: str = Field("linear", description="插值方法")


# ---------- Identification / 辨识 ----------

class IdentificationRequest(BaseModel):
    observed_h: list[float] = Field(..., min_length=3, max_length=100000, description="观测水位")
    observed_q_out: list[float] = Field(..., min_length=3, max_length=100000, description="观测出流量")
    model_type: str = Field("nonlinear", description="模型类型")
    initial_guess: dict | None = Field(None, description="初始猜测")


class ARXRequest(BaseModel):
    y: list[float] = Field(..., min_length=4, max_length=100000, description="输出时序")
    u: list[float] = Field(..., min_length=4, max_length=100000, description="输入时序")
    na: int = Field(2, ge=1, le=100, description="自回归阶数")
    nb: int = Field(2, ge=1, le=100, description="外源输入阶数")


# ---------- Skills / 技能 ----------

class SkillRequest(BaseModel):
    skill_name: str = Field(..., min_length=1, max_length=200, description="技能名称")
    params: dict = Field(default_factory=dict, description="技能参数")


class FourPredRequest(BaseModel):
    water_level_data: list[float] = Field(..., min_length=2, max_length=100000, description="水位数据")
    inflow_data: list[float] | None = Field(None, description="入流量数据")
    risk_threshold: float = Field(0.7, ge=0.0, le=1.0, description="风险阈值")


# ---------- Assistant / 助手 ----------

class AssistantMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000, description="用户消息")
    role: str = Field("admin", description="用户角色")
    params: dict = Field(default_factory=dict, description="附加参数")
    history: list[dict] = Field(default_factory=list, max_length=100, description="对话历史")
