# HydroClaw 部署与飞书对接指南

**HydroClaw Deployment & Feishu Integration Guide**

本文档详细说明如何在你的服务器上部署 HydroClaw 水网智能工作台，并与飞书（Feishu/Lark）对接。

---

## 目录

1. [架构概览](#1-架构概览)
2. [环境准备](#2-环境准备)
3. [快速部署（3 步完成）](#3-快速部署)
4. [飞书应用创建](#4-飞书应用创建)
5. [飞书机器人对接](#5-飞书机器人对接)
6. [飞书告警推送](#6-飞书告警推送)
7. [飞书多维表格同步](#7-飞书多维表格同步)
8. [Nginx 反向代理（HTTPS）](#8-nginx-反向代理)
9. [Docker 部署](#9-docker-部署)
10. [验证与测试](#10-验证与测试)
11. [常见问题](#11-常见问题)

---

## 1. 架构概览

```
┌─────────────────────────────────────────────────────┐
│                    飞书开放平台                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ 机器人消息  │  │ 群告警Bot │  │ 多维表格 Bitable │   │
│  └─────┬────┘  └────┬─────┘  └────────┬─────────┘   │
│        │             │                 │              │
└────────┼─────────────┼─────────────────┼──────────────┘
         │ Webhook      │ Webhook         │ Open API
         ▼              ▼                 ▼
┌────────────────────────────────────────────────────────┐
│                  Nginx (HTTPS 反向代理)                  │
│              your-domain:443 → localhost:8000            │
└────────────────────┬───────────────────────────────────┘
                     ▼
┌────────────────────────────────────────────────────────┐
│              HydroClaw (FastAPI :8000)                   │
│                                                          │
│  /api/feishu/webhook    ← 接收飞书消息                    │
│  /api/feishu/alert      ← 推送告警卡片                    │
│  /api/feishu/sync/flush ← 同步多维表格                    │
│  /api/feishu/status     ← 集成状态检查                    │
│  /api/gateway/chat      ← AI 对话入口                    │
│  /api/gateway/skill     ← 技能调用                       │
│  /api/gateway/health    ← 健康检查                       │
│                                                          │
│  FeishuClient → Token管理 + 签名验证 + 重试              │
│  FeishuBotHandler → 消息路由 + 命令解析                   │
│  FeishuAlertSender → 告警卡片 + Webhook推送              │
│  FeishuBitableSync → 多维表格批量同步                     │
└────────────────────────────────────────────────────────┘
```

## 2. 环境准备

### 2.1 服务器要求

- **系统**: Linux (Ubuntu 20.04+ / CentOS 7+ / Debian 11+)
- **CPU**: 2 核+
- **内存**: 4 GB+
- **磁盘**: 20 GB+
- **网络**: 公网 IP 或域名（飞书回调需要公网可达）
- **端口**: 8000（应用）, 443（HTTPS, 可选但推荐）

### 2.2 软件依赖

```bash
# Python 3.11+
python3 --version  # 确保 3.11+

# pip
pip --version

# (可选) Docker
docker --version
docker-compose --version

# (推荐) Nginx
nginx -v
```

## 3. 快速部署

### 方式一：直接部署（最简单）

```bash
# 1. 克隆代码
git clone <your-repo-url> HydroMAS
cd HydroMAS

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入飞书凭据（见第4节）

# 3. 一键启动
./deploy.sh prod
```

服务启动后访问: `http://your-server:8000`

### 方式二：手动部署

```bash
# 1. 安装依赖
pip install -e ".[web,alumina]"

# 2. 配置环境变量
cp .env.example .env
vim .env  # 填入飞书凭据

# 3. 加载环境变量
source .env

# 4. 启动服务
uvicorn web.app:app --host 0.0.0.0 --port 8000 --workers 2
```

### 方式三：Docker 部署（推荐生产环境）

见第 9 节。

## 4. 飞书应用创建

### 4.1 创建企业自建应用

1. 打开 [飞书开放平台](https://open.feishu.cn/app)
2. 点击 **"创建自建应用"**
3. 填写：
   - 应用名称：`HydroClaw 水网助手`
   - 应用描述：`水网智能工作台 AI 助手`
4. 创建完成后记录：
   - **App ID** → 填入 `.env` 的 `FEISHU_APP_ID`
   - **App Secret** → 填入 `.env` 的 `FEISHU_APP_SECRET`

### 4.2 开通机器人能力

1. 进入应用 → **添加应用能力** → **机器人**
2. 配置消息回调地址（需要先完成部署，第 5 节）

### 4.3 配置权限

在应用 **权限管理** 中开通以下权限：

| 权限 | 说明 | 用途 |
|------|------|------|
| `im:message:send_as_bot` | 以机器人身份发送消息 | 回复用户消息 |
| `im:message:receive_v1` | 接收消息事件 | 接收用户发送的消息 |
| `bitable:app` | 多维表格读写 | 数据同步到多维表格 |

### 4.4 发布应用

1. 应用 → **版本管理与发布** → **创建版本** → **提交审核**
2. 管理员审批通过后即可使用

## 5. 飞书机器人对接

### 5.1 配置事件订阅

1. 应用 → **事件与回调** → **事件配置**
2. 请求地址配置：
   ```
   https://your-domain/api/feishu/webhook
   ```
   （如果还没有 HTTPS，先用 `http://your-ip:8000/api/feishu/webhook`）
3. 飞书会发送一个 `challenge` 验证请求，HydroClaw 会自动响应
4. 记录：
   - **Verification Token** → 填入 `.env` 的 `FEISHU_VERIFICATION_TOKEN`
   - **Encrypt Key**（如果开启）→ 填入 `.env` 的 `FEISHU_ENCRYPT_KEY`

### 5.2 订阅事件

添加以下事件：
- `im.message.receive_v1` — 接收消息

### 5.3 更新 .env

```bash
# .env 飞书部分
FEISHU_APP_ID=cli_xxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
FEISHU_VERIFICATION_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxx
FEISHU_ENCRYPT_KEY=                   # 可选，如果在飞书后台开启了加密
FEISHU_WEBHOOK_URL=https://your-domain/api/feishu/webhook
```

### 5.4 机器人使用

配置完成后，在飞书群中 @机器人 或私聊机器人即可使用：

**自然语言对话：**
```
@HydroClaw 今天水平衡情况怎么样？
@HydroClaw 分析一下蒸发损失
@HydroClaw 检查系统安全状态
```

**命令快捷方式：**
```
/水平衡         → 全厂水平衡分析
/蒸发           → 蒸发优化分析
/泄漏           → 泄漏诊断
/调度           → 全局调度优化
/日报           → 生成日报
/预报           → 水位预报
/预警           → 预警分析
/ODD            → ODD 安全检查
```

英文命令也支持：`/balance`, `/evap`, `/leak`, `/dispatch`, `/report`

## 6. 飞书告警推送

### 6.1 创建群机器人 Webhook

1. 打开一个飞书群 → **设置** → **群机器人** → **添加机器人**
2. 选择 **自定义机器人**
3. 设置名称：`HydroClaw 告警`
4. 复制 Webhook 地址 → 填入 `.env` 的 `FEISHU_ALERT_WEBHOOK_URL`

```bash
FEISHU_ALERT_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

### 6.2 触发告警

告警通过 API 触发，当 SafetyAgent 检测到异常时自动推送：

```bash
# 手动触发告警测试
curl -X POST http://localhost:8000/api/feishu/alert \
  -H "Content-Type: application/json" \
  -d '{
    "alert_id": "TEST-001",
    "severity": "warning",
    "dimension": "water_level",
    "message": "一号水池水位异常偏高",
    "value": 0.98,
    "threshold": 0.95
  }'
```

### 6.3 告警卡片效果

告警会以飞书交互卡片形式推送到群内，包含：
- 告警级别（Info/Warning/Critical）及对应颜色
- 时间、来源、维度、当前值、阈值
- 操作按钮（一键诊断、人工确认、忽略）

## 7. 飞书多维表格同步

### 7.1 创建多维表格

1. 在飞书中创建一个 **多维表格**
2. 复制 URL 中的 `app_token`：
   ```
   https://xxx.feishu.cn/base/xxxAPP_TOKENxxx?table=...
   ```
3. 填入 `.env`：
   ```
   FEISHU_BITABLE_APP_TOKEN=xxxAPP_TOKENxxx
   ```

### 7.2 创建数据表

HydroClaw 预定义了 4 张表，你可以在多维表格中创建它们：

| 表名 | 中文 | 字段 |
|------|------|------|
| pipeline_runs | 开发流水线 | pipeline_id, requirement, status, planning_status, review_status, testing_status, iteration, created_at, completed_at |
| water_kpi | 水网 KPI | date, daily_intake, daily_reuse, reuse_rate, daily_evaporation, pump_energy, residual, anomaly_count |
| alerts | 告警记录 | alert_id, severity, dimension, value, threshold, message, timestamp, resolved |
| dev_tasks | 开发任务 | task_id, description, assignee, status, priority, module, due_date |

### 7.3 同步数据

```bash
# 查看表结构定义
curl http://localhost:8000/api/feishu/sync/schemas

# 手动刷新（推送待同步记录到飞书）
curl -X POST http://localhost:8000/api/feishu/sync/flush
```

## 8. Nginx 反向代理

飞书 Webhook 回调需要 HTTPS，推荐使用 Nginx + Let's Encrypt。

### 8.1 安装 Nginx

```bash
# Ubuntu/Debian
sudo apt install nginx certbot python3-certbot-nginx

# CentOS
sudo yum install nginx certbot python3-certbot-nginx
```

### 8.2 配置 Nginx

```nginx
# /etc/nginx/conf.d/hydroclaw.conf

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (for future use)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeout for long AI requests
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }
}
```

### 8.3 配置 HTTPS (Let's Encrypt)

```bash
# 自动获取证书并配置 HTTPS
sudo certbot --nginx -d your-domain.com

# 自动续期（crontab）
0 2 * * 1 certbot renew --quiet
```

### 8.4 如果没有域名

如果只有 IP 地址，可以暂时使用 HTTP。飞书开放平台允许 HTTP 回调地址用于开发测试。

将回调地址设为：`http://your-ip:8000/api/feishu/webhook`

> 注意：生产环境强烈建议使用 HTTPS。

## 9. Docker 部署

### 9.1 基本 Docker 部署

```bash
# 1. 配置环境变量
cp .env.example .env
vim .env  # 填入飞书凭据

# 2. 构建并启动
docker-compose up -d

# 3. 查看状态
docker-compose ps

# 4. 查看日志
docker-compose logs -f hydromas
```

### 9.2 包含 OpenClaw 实例

```bash
# 启动核心 + OpenClaw 基础实例
docker-compose --profile openclaw up -d

# 启动全部（含 peer/dev 实例）
docker-compose --profile openclaw --profile openclaw-full up -d
```

### 9.3 服务端口

| 服务 | 端口 | 用途 |
|------|------|------|
| HydroClaw | 8000 | FastAPI 主服务 |
| TDengine | 6041 | 时序数据库 REST |
| Neo4j | 7474 / 7687 | 图数据库 Web / Bolt |

### 9.4 数据持久化

Docker Compose 自动创建以下 volumes：
- `hydroclaw_sessions` — 会话数据
- `hydroclaw_memory` — 记忆数据
- `hydroclaw_interactions` — 交互日志
- `tdengine_data` — 时序数据
- `neo4j_data` — 图数据

## 10. 验证与测试

### 10.1 健康检查

```bash
# 应用健康检查
curl http://localhost:8000/api/gateway/health

# 飞书集成状态
curl http://localhost:8000/api/feishu/status
```

返回示例：
```json
{
  "client": {
    "app_id_configured": true,
    "app_secret_configured": true,
    "verification_token_configured": true,
    "encrypt_key_configured": false
  },
  "bot": {
    "ready": true,
    "webhook_url_configured": true,
    "commands": ["/水平衡", "/蒸发", "/泄漏", ...]
  },
  "alert": {
    "ready": true,
    "webhook_url_configured": true,
    "history_count": 0
  },
  "sync": {
    "ready": true,
    "app_token_configured": true,
    "table_schemas": ["pipeline_runs", "water_kpi", "alerts", "dev_tasks"]
  }
}
```

### 10.2 测试机器人对话

```bash
# 模拟飞书 Webhook 调用
curl -X POST http://localhost:8000/api/feishu/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "raw_body": {
      "event": {
        "message": {
          "message_id": "test_001",
          "chat_id": "oc_test",
          "message_type": "text",
          "content": "{\"text\": \"你好\"}"
        },
        "sender": {
          "sender_id": {"user_id": "test_user"}
        }
      }
    }
  }'
```

### 10.3 测试告警推送

```bash
curl -X POST http://localhost:8000/api/feishu/alert \
  -H "Content-Type: application/json" \
  -d '{
    "severity": "warning",
    "dimension": "water_level",
    "message": "测试告警",
    "value": 0.95,
    "threshold": 0.90
  }'
```

### 10.4 运行单元测试

```bash
# 运行所有飞书相关测试
pytest tests/test_integrations/ -v

# 只运行客户端测试
pytest tests/test_integrations/test_feishu_client.py -v
```

## 11. 常见问题

### Q: 飞书 Webhook 验证失败？

**A**: 检查以下几点：
1. 确认服务已启动：`curl http://localhost:8000/api/gateway/health`
2. 确认公网可达：从外部访问 `http://your-ip:8000/api/feishu/webhook`
3. 确认 `.env` 中 `FEISHU_VERIFICATION_TOKEN` 与飞书后台一致
4. 如果使用 Nginx，确认代理配置正确

### Q: 机器人收到消息但不回复？

**A**: 查看日志：
```bash
# 直接部署
grep "FeishuBot" /var/log/hydromas/app.log

# Docker 部署
docker-compose logs -f hydromas | grep FeishuBot
```

常见原因：
- 未开通 `im:message:send_as_bot` 权限
- `FEISHU_APP_SECRET` 配置错误导致 token 获取失败

### Q: 告警没有推送到群？

**A**: 检查 `.env` 中 `FEISHU_ALERT_WEBHOOK_URL` 是否正确。测试方式：
```bash
# 直接用 curl 测试群 webhook
curl -X POST "YOUR_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{"msg_type":"text","content":{"text":"Hello from HydroClaw"}}'
```

### Q: 多维表格同步失败？

**A**: 检查：
1. `FEISHU_BITABLE_APP_TOKEN` 是否正确（从多维表格 URL 中获取）
2. 应用是否开通了 `bitable:app` 权限
3. 确认多维表格中有对应的数据表

### Q: 如何更新部署？

```bash
# 拉取最新代码
git pull

# 直接部署
./deploy.sh prod

# Docker 部署
docker-compose build && docker-compose up -d
```

### Q: 如何查看系统状态？

```bash
# 综合健康检查
curl http://localhost:8000/api/gateway/health

# 飞书集成状态
curl http://localhost:8000/api/feishu/status

# AI 对话测试
curl -X POST http://localhost:8000/api/gateway/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "你好", "role": "admin"}'
```

---

## 快速参考

### .env 配置清单

```bash
# 必填
FEISHU_APP_ID=cli_xxxx               # 飞书开放平台 → 应用凭证
FEISHU_APP_SECRET=xxxx               # 同上

# 推荐填写
FEISHU_VERIFICATION_TOKEN=xxxx       # 事件订阅 → Verification Token
FEISHU_WEBHOOK_URL=https://xxx/api/feishu/webhook  # 你的回调地址
FEISHU_ALERT_WEBHOOK_URL=https://xxx # 群自定义机器人 Webhook

# 可选
FEISHU_ENCRYPT_KEY=                  # 加密密钥（如开启加密）
FEISHU_BITABLE_APP_TOKEN=            # 多维表格 app_token
```

### API 端点一览

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/feishu/webhook` | POST | 飞书消息回调 |
| `/api/feishu/alert` | POST | 推送告警 |
| `/api/feishu/alert/history` | GET | 告警历史 |
| `/api/feishu/sync/flush` | POST | 同步到多维表格 |
| `/api/feishu/sync/schemas` | GET | 表结构定义 |
| `/api/feishu/status` | GET | 集成状态 |
| `/api/gateway/chat` | POST | AI 对话 |
| `/api/gateway/skill` | POST | 技能调用 |
| `/api/gateway/health` | GET | 健康检查 |
