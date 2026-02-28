---
name: hydromas-assistant
description: |
  HydroMAS 水网智能助理 — 连接 HydroMAS 多智能体平台。支持：
  - 水位预报、预警、预演、预案 (四预系统)
  - ODD安全检查、泄漏检测、水平衡核算
  - 调度优化、蒸发预测、回用优化
  - 日运营报告、全生命周期分析
  - 仿真模拟、控制设计、参数辨识
  Use when user asks about: 水位, 预报, 预警, ODD, 泄漏, 水平衡, 调度,
  蒸发, 回用, 日报, 仿真, 控制设计, water level, forecast, dispatch, leak
homepage: https://github.com/leixiaohui-1974/HydroMAS
metadata:
  openclaw:
    emoji: "💧"
    requires:
      bins: [python3, curl]
      env: [HYDROMAS_URL]
    primaryEnv: HYDROMAS_URL
---

# HydroMAS 水网智能助理

连接 HydroMAS 多智能体智能决策平台，为科研、设计、运维提供水网全生命周期管理能力。

## Architecture

```
OpenClaw (你) → HydroMAS Gateway API → 15 Agent + 17 Skill + 13 MCP Server
```

## 三种角色模式

| 角色 | 说明 | 核心能力 |
|------|------|---------|
| **operator** (运维) | 日常运营监控调度 | 四预系统、ODD检查、调度、日报、泄漏检测、水平衡 |
| **designer** (设计) | 系统设计优化 | 控制设计、优化设计、敏感性分析、蒸发优化、回用优化 |
| **researcher** (科研) | 科研分析建模 | 仿真模拟、数据分析、预测评价、系统辨识、WNAL评估 |

## Usage

### 自然语言对话

通过 HydroMAS Gateway 发送自然语言请求：

```bash
curl -X POST ${HYDROMAS_URL}/api/gateway/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "检查今天水平衡", "role": "operator"}'
```

### 执行指定技能

```bash
curl -X POST ${HYDROMAS_URL}/api/gateway/skill \
  -H "Content-Type: application/json" \
  -d '{"skill_name": "daily_report", "params": {"date": "2026-02-28"}}'
```

### 查看可用技能

```bash
curl ${HYDROMAS_URL}/api/gateway/skills?role=operator
```

### 健康检查

```bash
curl ${HYDROMAS_URL}/api/gateway/health
```

### Python SDK

```python
# Copy hydromas_client.py to your OpenClaw workspace, then:
from hydromas_client import HydroMASClient

client = HydroMASClient("http://localhost:8000")

# 自然语言对话
result = client.chat("生成今日运营报告", role="operator")
print(result.to_markdown())

# 直接调用技能
result = client.run_skill("forecast_skill", {"horizon": 24})

# 角色快捷操作
actions = client.get_role_actions("operator")
```

## Available Skills (17)

### 运维技能
- `forecast_skill` — 水位预报
- `warning_skill` — 水位预警
- `rehearsal_skill` — 预演仿真
- `plan_skill` — 应急预案
- `four_prediction_loop` — 四预闭环
- `daily_report` — 日运营报告
- `leak_diagnosis` — 泄漏检测诊断
- `global_dispatch` — 全局调度优化

### 设计技能
- `control_system_design` — 控制系统设计
- `optimization_design` — 优化设计
- `odd_assessment` — ODD安全评估
- `evap_optimization` — 蒸发优化
- `reuse_scheduling` — 回用调度

### 科研技能
- `data_analysis_predict` — 数据分析预测
- `full_lifecycle` — 全生命周期分析

### 内容技能
- `content_pipeline` — 内容流水线 (写作→审查→发布)
- `collaborative_dev` — 协作开发

## Environment Variables

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `HYDROMAS_URL` | HydroMAS 服务地址 | `http://localhost:8000` |

## Notes

- HydroMAS 运行在同一台服务器的 8000 端口
- 所有 API 返回 JSON 格式
- 对话接口支持意图分类，自动路由到最合适的技能
- 角色参数影响返回结果的专业度和侧重点
