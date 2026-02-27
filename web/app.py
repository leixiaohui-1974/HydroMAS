"""FastAPI application — HydroOS-Agent Web Platform.
FastAPI 应用 — HydroOS-Agent Web 平台。

Usage:
    uvicorn web.app:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from web.routers import (
    assistant,
    control,
    dataclean,
    design,
    dispatch,
    evaluation,
    evaporation,
    identification,
    leak_detection,
    odd,
    orchestration,
    prediction,
    report,
    reuse,
    scheduling,
    simulation,
    skills,
    water_balance,
)

logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).parent

_is_prod = os.environ.get("ENV", "development") == "production"

app = FastAPI(
    title="HydroOS-Agent",
    description="多智能体智能决策平台 — Multi-Agent Intelligent Decision Platform",
    version="0.1.0",
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
)


# ---------- Security Headers Middleware / 安全头中间件 ----------

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "upgrade-insecure-requests"
        )
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)

# GZip compression for large simulation responses
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS — configurable via ALLOWED_ORIGINS env var; defaults to same-origin
_allowed_origins = os.environ.get("ALLOWED_ORIGINS", "").split(",")
_allowed_origins = [o.strip() for o in _allowed_origins if o.strip()] or ["http://localhost:8000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# ---------- Global Exception Handler / 全局异常处理 ----------

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Convert ValueError from core/MCP layer to 400 response."""
    detail = str(exc)
    if len(detail) > 200:
        detail = detail[:200] + "..."
    return JSONResponse(status_code=400, content={"detail": detail})


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all handler — log details, return generic message."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please check server logs."},
    )


# Mount static files and templates
app.mount("/static", StaticFiles(directory=_BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=_BASE_DIR / "templates")

# Register API routers
app.include_router(simulation.router, prefix="/api/simulation", tags=["Simulation / 仿真模拟"])
app.include_router(control.router, prefix="/api/control", tags=["Control / 控制管理"])
app.include_router(prediction.router, prefix="/api/prediction", tags=["Prediction / 智能预测"])
app.include_router(scheduling.router, prefix="/api/scheduling", tags=["Scheduling / 调度优化"])
app.include_router(evaluation.router, prefix="/api/evaluation", tags=["Evaluation / 性能评价"])
app.include_router(odd.router, prefix="/api/odd", tags=["ODD / 安全监测"])
app.include_router(design.router, prefix="/api/design", tags=["Design / 优化设计"])
app.include_router(dataclean.router, prefix="/api/dataclean", tags=["DataClean / 数据清洗"])
app.include_router(
    identification.router, prefix="/api/identification",
    tags=["Identification / 系统辨识"],
)
app.include_router(skills.router, prefix="/api/skills", tags=["Skills / 技能工作流"])
app.include_router(assistant.router, prefix="/api/assistant", tags=["Assistant / 智能助手"])
app.include_router(
    water_balance.router, prefix="/api/water-balance",
    tags=["Water Balance / 水平衡"],
)
app.include_router(
    leak_detection.router, prefix="/api/leak-detection",
    tags=["Leak Detection / 泄漏检测"],
)
app.include_router(evaporation.router, prefix="/api/evaporation", tags=["Evaporation / 蒸发预测"])
app.include_router(reuse.router, prefix="/api/reuse", tags=["Reuse / 回用优化"])
app.include_router(dispatch.router, prefix="/api/dispatch", tags=["Dispatch / 调度优化"])
app.include_router(report.router, prefix="/api/report", tags=["Report / 运营报告"])
app.include_router(
    orchestration.router, prefix="/api/orchestration",
    tags=["Orchestration / 多智能体编排"],
)


# ---------- User Roles / 用户角色 ----------

ROLES = {
    "operator": {
        "name": "调度运营",
        "name_en": "Operations",
        "icon": "activity",
        "modules": ["dashboard", "control", "fourpred", "odd", "reports"],
        "description": "实时监控、调度控制、四预系统、安全监测",
    },
    "engineer": {
        "name": "规划设计",
        "name_en": "Engineering",
        "icon": "cpu",
        "modules": ["dashboard", "simulation", "design", "control", "identification"],
        "description": "仿真模拟、系统设计、敏感性分析、参数辨识",
    },
    "analyst": {
        "name": "数据分析",
        "name_en": "Analysis",
        "icon": "bar-chart-2",
        "modules": ["dashboard", "prediction", "data", "evaluation", "reports"],
        "description": "智能预测、数据清洗、性能评价、报告生成",
    },
    "admin": {
        "name": "系统管理",
        "name_en": "Administration",
        "icon": "shield",
        "modules": [
            "dashboard", "simulation", "control", "prediction",
            "scheduling", "fourpred", "odd", "design", "data",
            "identification", "evaluation", "reports",
        ],
        "description": "全功能访问，系统配置与管理",
    },
}


@app.get("/")
async def index(request: Request):
    """Render main SPA page. / 渲染主单页应用。"""
    return templates.TemplateResponse(request, "index.html", {
        "roles": ROLES,
    })


@app.get("/api/roles")
async def get_roles():
    """Return available user roles. / 返回可用用户角色。"""
    return ROLES


@app.get("/api/system/status")
async def system_status():
    """Return system health summary. / 返回系统健康状态摘要。"""
    from core.config import load_odd_specs, load_tank_config

    config = load_tank_config()
    odd_specs = load_odd_specs()

    return {
        "status": "online",
        "tank_config_loaded": bool(config),
        "odd_dimensions": len(odd_specs.get("dimensions", [])),
        "version": "0.1.0",
        "layers": {
            "L0_core": "operational",
            "L1_compute": "operational",
            "L2_mcp_servers": "operational",
            "L3_skills": "operational",
            "L4_agents": "operational",
        },
    }
