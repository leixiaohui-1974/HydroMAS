# HydroMAS 产品落地战略分析

## 目录

1. [懒猫微服产品线对比分析](#一懒猫微服产品线对比分析)
2. [高校服务器启动策略](#二高校服务器启动策略)
3. [科研团队的独立与共享](#三科研团队的独立与共享)
4. [飞书深度集成策略](#四飞书深度集成策略)
5. [调度中心与现场运维视角](#五调度中心与现场运维视角)
6. [面向科研/设计/运维的测试案例](#六面向科研设计运维的测试案例)

---

## 一、懒猫微服产品线对比分析

### 1.1 产品线一览

| 产品 | 定位 | 核心硬件 | 价格 | 适用场景 |
|------|------|----------|------|----------|
| **LC-02** | 家庭私有云微服务器 | Intel AI 芯片, 16/32GB RAM, 2/8TB SSD | ¥5,399~8,899 | 个人开发者、小型团队、数据存储 |
| **LC-03** | AI 数据中心 | 高性能标压处理器, 7盘位全固态, 96TB | 待确认（预估¥8,000+） | 团队协作、中型数据存储、应用托管 |
| **AI 算力舱 X3** | 专用 AI 推理设备 | Jetson Orin 64GB, 275 TOPS, 60W | 预估¥8,000~12,000 | AI 模型推理、边缘计算、知识库 |

### 1.2 与传统 NAS 对比

| 对比维度 | 懒猫微服 LC-03 | 群晖 DS923+ | 威联通 TS-464C2 |
|----------|---------------|------------|-----------------|
| **定位** | 私有云 + AI 服务器 | 专业 NAS | 专业 NAS |
| **AI 能力** | 本地 LLM + 可扩展算力舱 | 有限（Synology AI） | 有限 |
| **内网穿透** | 零配置、开箱即用 | QuickConnect（限速） | myQNAPcloud |
| **RAID** | 暂不支持 | 完善（SHR/RAID 5/6） | 完善 |
| **生态成熟度** | 新兴（2年） | 成熟（20+年） | 成熟（20+年） |
| **Docker** | 支持 | 支持 | 支持 |
| **价格** | ¥5,399 起 | ¥4,500+ | ¥3,299+ |

### 1.3 对 HydroMAS 的适用性分析

**推荐组合：LC-03 + AI 算力舱 X3**

- **LC-03 作为数据中心**：托管 HydroMAS Web 平台（FastAPI）、TDengine 时序数据库、Neo4j 图数据库；7盘位全固态 + 96TB 容量满足水网历史数据存储
- **AI 算力舱 X3 作为推理引擎**：64GB 显存可运行瀚铎水网大模型（HanduoAgent）；275 TOPS 算力支持 GNN 泄漏检测实时推理；60W 功耗适合 7×24 边缘部署
- **内网穿透**：现场运维人员无需 VPN 即可远程访问调度系统
- **组网扩展**：多台算力舱通过局域网叠加算力，适合训练场景

**局限性**：
- 不支持 RAID，关键生产数据需额外备份方案
- 非 x86 架构（Jetson 为 ARM），需验证全部依赖兼容性
- 生态较新，企业级运维工具链不如群晖成熟

---

## 二、高校服务器启动策略

### 2.1 资源分析

假设学校拥有几百万元级别的服务器集群（典型配置：多台 GPU 服务器 + 存储阵列 + 高速网络），这是极其宝贵的初始资源。

### 2.2 分层部署架构

```
┌──────────────────────────────────────────────────────┐
│                    高校数据中心                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ GPU 集群  │  │ 存储集群  │  │   管理节点        │   │
│  │ (训练)   │  │ (数据湖) │  │ (Slurm/K8s)     │   │
│  └────┬─────┘  └────┬─────┘  └────────┬─────────┘   │
│       │             │                  │              │
│  ┌────┴─────────────┴──────────────────┴──────────┐  │
│  │           内部高速网络 (InfiniBand/25GbE)        │  │
│  └────────────────────┬───────────────────────────┘  │
│                       │                              │
│  ┌────────────────────┴──────────────────────────┐   │
│  │          HydroMAS 服务层                       │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌───────┐  │   │
│  │  │Web平台 │ │MCP     │ │Agent   │ │知识库  │  │   │
│  │  │FastAPI │ │Servers │ │System  │ │RAG    │  │   │
│  │  └────────┘ └────────┘ └────────┘ └───────┘  │   │
│  └───────────────────────────────────────────────┘   │
└──────────────────────────┬───────────────────────────┘
                           │ 校园网 / VPN
              ┌────────────┴────────────┐
              │                         │
     ┌────────┴────────┐      ┌────────┴────────┐
     │  教师/研究生     │      │  合作企业        │
     │  (科研+教学)    │      │  (设计/运维)     │
     └─────────────────┘      └─────────────────┘
```

### 2.3 四阶段启动路线图

**第一阶段：基础部署（1-2个月）**
- 在 1-2 台 GPU 服务器上部署 HydroMAS 全栈（Docker Compose）
- 配置 Slurm 队列：`hydromas-dev`（开发）、`hydromas-train`（训练）、`hydromas-prod`（生产）
- 搭建共享存储（NFS/BeeGFS），统一数据目录
- 导入双容水箱示范数据 + 氧化铝厂历史数据

**第二阶段：团队赋能（2-4个月）**
- 为每位研究生配置独立的开发命名空间（Slurm account + 独立工作目录）
- 部署 JupyterHub，集成 HydroMAS Python SDK
- 搭建飞书知识库 + 项目管理多维表格
- 开展内部培训：核心算法、API 使用、测试框架

**第三阶段：产品打磨（4-8个月）**
- 利用 GPU 集群训练 GNN 泄漏检测模型 + RL 调度策略
- 瀚铎大模型微调（利用水网领域知识库）
- 基于真实数据的 A/B 测试和性能评估
- 撰写论文、申报专利，形成学术成果

**第四阶段：对外推广（8-12个月）**
- 在懒猫微服 LC-03 + AI 算力舱上部署边缘版本
- 与合作企业（氧化铝厂、水务公司）建立试点
- 通过飞书开放平台提供 SaaS 服务
- 学校服务器作为"算力母舰"，边缘设备作为"前哨站"

### 2.4 成本效益分析

| 方案 | 前期投入 | 月度成本 | 适用阶段 |
|------|---------|---------|---------|
| 高校服务器自有 | ¥0（已有） | 电费 + 运维人力 | 研发+训练 |
| 云 GPU（阿里云/火山引擎） | ¥0 | ¥3,000-10,000/月 | 弹性扩展 |
| 懒猫微服 LC-03 + X3 | ¥15,000-20,000 | 电费 <¥50/月 | 边缘部署/演示 |
| 混合方案（推荐） | ¥15,000-20,000 | ¥1,000-3,000/月 | 全生命周期 |

**核心策略**：用学校服务器做"重活"（训练、大规模仿真），用懒猫微服做"轻活"（推理、演示、边缘部署），形成互补。

---

## 三、科研团队的独立与共享

### 3.1 核心矛盾

| 需求 | 独立性要求 | 共享性要求 |
|------|-----------|-----------|
| **数据** | 未发表数据需保密 | 公共数据集应共享复用 |
| **代码** | 个人实验代码随意修改 | 核心框架统一维护 |
| **算力** | 紧急任务需优先保障 | 闲置资源应充分利用 |
| **成果** | 论文署名归属清晰 | 技术积累团队共享 |

### 3.2 大学/科研单位团队模式

**典型场景**：导师带 5-10 名研究生，每人一个研究方向

```
┌────────────────────────────────────────────────────┐
│                  HydroMAS 团队架构                   │
│                                                    │
│  ┌──────────────────────────────────────────────┐  │
│  │  共享层 (Team Shared)                         │  │
│  │  • core/ — 核心算法库（统一维护）              │  │
│  │  • data/public/ — 公共数据集                   │  │
│  │  • knowledge/ — 领域知识库                     │  │
│  │  • tests/ — 统一测试框架                       │  │
│  │  • 飞书知识库 — 文档、会议记录、文献综述       │  │
│  └──────────────────────────────────────────────┘  │
│                                                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ 研究生A  │ │ 研究生B  │ │ 研究生C  │  ...     │
│  │ 泄漏检测 │ │ 蒸发优化 │ │ 调度策略 │          │
│  │ ──────── │ │ ──────── │ │ ──────── │          │
│  │ 私有分支 │ │ 私有分支 │ │ 私有分支 │          │
│  │ 私有数据 │ │ 私有数据 │ │ 私有数据 │          │
│  │ 实验笔记 │ │ 实验笔记 │ │ 实验笔记 │          │
│  └──────────┘ └──────────┘ └──────────┘          │
│                                                    │
│  数据流向：私有 → 验证通过 → 合并到共享层          │
│  成果流向：实验 → 论文 → 开源/专利 → 产品化        │
└────────────────────────────────────────────────────┘
```

**HydroMAS 支撑机制**：

| 机制 | 实现方式 | 独立/共享 |
|------|---------|----------|
| **Git 分支策略** | `main`（稳定）→ `dev/*`（个人）→ PR 合并 | 独立开发，共享集成 |
| **Slurm 账户隔离** | 每人独立 account + 共享 partition | 独立算力，弹性共享 |
| **数据目录** | `/shared/data/` + `/home/user/private/` | 三级权限（公开/团队/私有） |
| **飞书多维表格** | 项目看板 + 个人任务列表 | 进度可见，任务独立 |
| **MCP Server** | 每个 Server 独立部署、独立开发 | 接口统一，实现独立 |
| **Agent 系统** | Orchestrator 统一调度 + 专项 Agent 独立 | 整体协调，局部自治 |

**关键流程**：
1. **周会**：飞书视频会 + 多维表格更新进度
2. **代码评审**：GitHub PR + CI 自动化测试（1001 tests）
3. **数据共享**：通过 MCP Server 提供标准化 API，而非直接共享文件
4. **成果管理**：飞书文档统一管理论文草稿、实验记录

### 3.3 设计院团队模式

**典型场景**：项目经理 + 3-5 名设计工程师，承接工程项目

```
┌────────────────────────────────────────────────────┐
│                 设计院 HydroMAS 使用模式              │
│                                                    │
│  ┌────────────────────────────────────────────┐    │
│  │  项目层 (Project Level)                     │    │
│  │  • 项目A：XX 氧化铝厂水网改造设计           │    │
│  │  • 项目B：XX 水务公司调度系统设计           │    │
│  │  • 项目C：XX 园区给排水规划                 │    │
│  └────────────────────────────────────────────┘    │
│                     │                              │
│  ┌─────────────────┴──────────────────────────┐    │
│  │  平台层 (Platform Level)                    │    │
│  │  • HydroMAS 核心引擎（只读使用）            │    │
│  │  • 设计计算模板库                           │    │
│  │  • 标准规范知识库 (GB/T, HJ)                │    │
│  │  • 历史工程案例库                           │    │
│  └────────────────────────────────────────────┘    │
│                                                    │
│  工作流：需求分析 → 方案比选 → 详细设计 → 校审     │
│  工具链：飞书文档(写作) + HydroMAS(建模) + 飞书项目(管理) │
└────────────────────────────────────────────────────┘
```

**设计院特殊需求**：
- **质量管控**：设计文件需经"设计→校核→审核→审定"四级流程
- **版本管理**：设计变更需追溯，HydroMAS 的 Git 版本控制天然支持
- **标准引用**：RAG 知识库集成国标、行标文本
- **成果复用**：项目间共享设计模板，但数据严格隔离（甲方保密）
- **资质管理**：飞书多维表格管理设计师资质证书到期提醒

---

## 四、飞书深度集成策略

### 4.1 飞书功能矩阵与 HydroMAS 映射

```
飞书功能         →  HydroMAS 集成点           →  使用角色
─────────────────────────────────────────────────────────
飞书文档         →  论文/报告协同写作          →  科研人员
飞书多维表格     →  项目管理 + 数据展示        →  全员
飞书知识库       →  领域知识 + RAG 数据源      →  全员
飞书机器人       →  告警推送 + AI 对话入口     →  运维/调度
飞书审批         →  设计文件校审流程           →  设计人员
飞书日历         →  维护计划 + 会议安排        →  运维/管理
飞书视频会议     →  远程诊断 + 专家会商        →  全员
飞书开放平台     →  Webhook + API 集成        →  开发人员
飞书低代码       →  快速搭建轻量应用          →  业务人员
```

### 4.2 核心集成架构

```
┌────────────────────────────────────────────────────┐
│                    飞书平台                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │ 飞书机器人│ │多维表格   │ │ 知识库           │   │
│  │ (告警+AI)│ │(项目管理) │ │ (RAG数据源)     │   │
│  └────┬─────┘ └────┬─────┘ └────────┬─────────┘   │
│       │            │                │              │
│  ┌────┴────────────┴────────────────┴──────────┐   │
│  │         飞书开放平台 API / Webhook            │   │
│  └────────────────────┬────────────────────────┘   │
└───────────────────────┼────────────────────────────┘
                        │ HTTPS
┌───────────────────────┼────────────────────────────┐
│  HydroMAS 集成层       │                            │
│  ┌────────────────────┴────────────────────────┐   │
│  │         Feishu Integration Service           │   │
│  │  • feishu_bot.py  — 消息收发 + 命令解析     │   │
│  │  • feishu_sync.py — 多维表格双向同步        │   │
│  │  • feishu_rag.py  — 知识库文档索引          │   │
│  │  • feishu_alert.py — 告警推送               │   │
│  └─────────────────────────────────────────────┘   │
│       ↕                ↕                ↕           │
│  ┌─────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Agents  │  │ MCP Servers  │  │ Knowledge    │  │
│  │ 系统    │  │              │  │ RAG Service  │  │
│  └─────────┘  └──────────────┘  └──────────────┘  │
└────────────────────────────────────────────────────┘
```

### 4.3 六大飞书集成场景

#### 场景1：飞书机器人 → HydroMAS AI 对话

```
运维人员在飞书群中：
  @水网助手 当前水平衡状态如何？
  → 飞书机器人 → HydroMAS Orchestrator → water_balance MCP
  → 返回：各节点残差图 + 异常告警

  @水网助手 请生成今日运行日报
  → 飞书机器人 → DailyReportSkill
  → 返回：Markdown 格式日报 → 自动发送到飞书文档
```

#### 场景2：多维表格 → 项目管理

```
飞书多维表格 "HydroMAS 研发看板"
├── 视图1：甘特图（任务时间线）
├── 视图2：看板（To Do / In Progress / Done）
├── 视图3：表格（负责人、优先级、截止日期）
└── 自动化规则：
    • 任务状态变更 → Webhook → 触发 CI/CD
    • 到期提醒 → 飞书通知相关人
    • 新建任务 → 自动关联 Git Issue
```

#### 场景3：知识库 → RAG 增强

```python
# 飞书知识库文档 → HydroMAS RAG 索引
# 水网设计规范 (GB 50015, GB 50013)
# 氧化铝生产工艺手册
# 历史故障案例库
# 团队论文和技术报告

# RAGService 自动从飞书知识库同步
rag = RAGService()
rag.sync_from_feishu(space_id="xxx")
answer = rag.query("氧化铝厂冷却塔蒸发量计算公式？")
```

#### 场景4：审批流 → 设计校审

```
设计工程师提交水网设计方案
→ 飞书审批流（设计→校核→审核→审定）
→ 每步审批时自动调用 HydroMAS 检查：
   • ODD 安全边界校验
   • 水平衡一致性检查
   • 设备选型参数合规性
→ 审批通过后自动归档到飞书知识库
```

#### 场景5：告警推送 → 实时监控

```
HydroMAS SafetyAgent 检测到异常
→ feishu_alert.py → 飞书群告警卡片
   ┌────────────────────────────────┐
   │ ⚠ 水平衡异常告警              │
   │ 时间：2026-02-27 14:30:00     │
   │ 节点：冷却塔循环回路           │
   │ 残差：+180 m³/d（阈值 ±50）   │
   │ 可能原因：管道泄漏             │
   │ [查看详情] [一键诊断] [忽略]   │
   └────────────────────────────────┘
→ 点击 [一键诊断] → 触发 LeakDiagnosisSkill
```

#### 场景6：Webhook → 自动化流水线

```
Git Push → GitHub Webhook → 飞书多维表格更新测试状态
飞书审批通过 → Webhook → HydroMAS 执行计算任务
定时器 → Webhook → 每日自动生成水平衡报告
外部 SCADA 数据 → Webhook → 多维表格实时数据看板
```

### 4.4 飞书 + Clawdbot + HydroMAS 融合构想

Clawdbot（OpenClaw）作为开源 AI 助手网关，可以桥接飞书与 HydroMAS：

```
飞书消息 → Clawdbot Gateway → HydroMAS Agent System
                ↓
         长期记忆（Markdown 文件）
                ↓
         多平台同步（飞书 + Telegram + Web）
```

这样实现：在飞书中自然语言对话，Clawdbot 调用 HydroMAS 的 MCP Server 执行实际计算，结果以飞书卡片形式返回。

---

## 五、调度中心与现场运维视角

### 5.1 调度中心视角

**角色**：中控室值班调度员，负责全厂水网统筹

```
┌──────────────────────────────────────────────────────────┐
│                     调度中心大屏                           │
│  ┌───────────────────┐  ┌────────────────────────────┐   │
│  │   水网拓扑实时图    │  │   水平衡仪表盘              │   │
│  │   (12 节点状态)    │  │   进水: 10,400 m³/d        │   │
│  │   绿=正常          │  │   蒸发: 4,200 m³/d         │   │
│  │   黄=预警          │  │   回用: 3,100 m³/d         │   │
│  │   红=告警          │  │   残差: +52 m³/d ⚠         │   │
│  └───────────────────┘  └────────────────────────────┘   │
│  ┌───────────────────┐  ┌────────────────────────────┐   │
│  │   调度建议         │  │   告警列表                  │   │
│  │   • 降低冷却塔风量 │  │   14:30 冷却塔残差异常      │   │
│  │   • 增加回用水比例 │  │   15:00 泵站能耗偏高        │   │
│  │   • 切换备用水源   │  │   [AI 诊断] [人工确认]      │   │
│  └───────────────────┘  └────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

**HydroMAS 为调度中心提供**：
1. **GlobalDispatchSkill**：需求预测 → 蒸发估算 → 全局调度 → ODD 检查
2. **RLDispatchAgent**：PPO/规则混合策略，每小时自动生成调度方案
3. **SafetyAgent**：12维 ODD 实时监控，越界自动触发 MRC
4. **飞书集成**：调度指令通过飞书审批流下发，可追溯

### 5.2 现场运维人员视角

**角色**：巡检工、维修工，在车间/管廊现场作业

```
运维人员手机端（飞书 App / HydroMAS 小程序）：

┌──────────────────────┐
│  今日巡检任务 (3/8)   │
│  ☑ 冷却塔水位检查     │
│  ☑ 泵站运行记录       │
│  ☑ 管道目视检查       │
│  ☐ 阀门开度确认       │
│  ☐ 水质取样           │
│  ...                  │
│                       │
│  [AI 助手] [扫码报修] │
└──────────────────────┘
```

**交互场景**：
```
运维人员：@水网助手 3号冷却塔出水温度偏高，42°C
AI 助手：  根据 Merkel 模型分析：
          • 正常范围：35-38°C
          • 当前蒸发效率下降 15%
          • 可能原因：填料结垢或风机减速
          • 建议：检查填料状态，确认风机转速
          [生成维修工单] [联系专家]

运维人员：点击 [生成维修工单]
→ 飞书审批流自动创建维修单
→ 相关人员收到通知
→ 维修完成后自动更新设备台账
```

### 5.3 角色协同矩阵

| 功能 | 科研人员 | 设计人员 | 调度中心 | 现场运维 |
|------|---------|---------|---------|---------|
| 四预闭环 | 算法开发 | 方案设计 | 日常使用 | 接收预警 |
| 泄漏诊断 | 模型训练 | 管网设计参考 | 触发诊断 | 现场确认 |
| 蒸发优化 | 论文研究 | 设备选型 | 策略执行 | 参数采集 |
| 水平衡 | 数据分析 | 校核计算 | 实时监控 | 数据录入 |
| 飞书知识库 | 论文/报告 | 规范/模板 | 操作手册 | 故障案例 |

---

## 六、面向科研/设计/运维的测试案例

### 核心理念

```
写作 + 建模 + 管理 = 科研
写作 + 建模 + 管理 = MBD 设计（Model-Based Design）
写作 + 建模       = 运维
```

三者的本质区别不在工具，而在**目标和流程**：
- **科研**：探索未知，产出论文/专利，需要可重复性验证
- **设计**：满足规范，产出设计文件，需要校审流程
- **运维**：保障运行，产出运行记录，需要实时响应

### 6.1 双容水箱系统测试案例

#### 案例 R1：科研场景 — 双容水箱 PID/MPC 对比论文

**目标**：撰写一篇关于双容水箱液位控制的学术论文

| 步骤 | 活动 | HydroMAS 工具 | 飞书集成 |
|------|------|--------------|---------|
| 1 | 文献综述 | RAGService 检索相关文献 | 飞书文档：综述稿 |
| 2 | 问题建模 | `TankParams + run_simulation` | 飞书多维表格：参数记录 |
| 3 | PID 设计 | `PIDController + 参数整定` | 实验记录表 |
| 4 | MPC 设计 | `MPCController + 优化求解` | 实验记录表 |
| 5 | 对比仿真 | `Rehearsal Skill（预演）` | 结果图表存飞书云盘 |
| 6 | ODD 分析 | `check_odd` 安全性评估 | 安全分析报告 |
| 7 | 论文撰写 | Report Agent 生成 Markdown | 飞书文档协作编辑 |
| 8 | 实验复现 | `pytest` 全自动化验证 | CI 结果推送飞书群 |

**测试验证点**：
```python
# R1-T1: 仿真参数可配置，结果可复现
params = get_default_tank_params()  # area=1.0, cd=0.6
result = run_simulation(params, dt=0.1, t_end=100)
assert result["final_level"] > 0

# R1-T2: PID 控制器在 ODD 边界内
pid = PIDController(kp=1.0, ki=0.1, kd=0.05)
# ... 闭环仿真
odd_result = check_odd({"water_level": final_h})
assert odd_result["zone"] == "green"

# R1-T3: MPC 优化目标函数可收敛
mpc = MPCController(horizon=10, dt=0.1)
# ... 滚动优化
assert mpc_cost[-1] < mpc_cost[0]  # 成本递减

# R1-T4: 论文图表自动生成
report = ReportAgent()
md_report = report.generate(data, template="paper_comparison")
assert "## Results" in md_report
```

#### 案例 D1：设计场景 — 双容水箱系统优化选型

**目标**：为某工程项目设计双容水箱系统的尺寸和设备参数

| 步骤 | 活动 | HydroMAS 工具 | 飞书集成 |
|------|------|--------------|---------|
| 1 | 需求分析 | `ProcessState` 工艺需求计算 | 飞书文档：设计任务书 |
| 2 | 水箱尺寸设计 | `design_tank` 容积优化 | 多维表格：方案比选 |
| 3 | 灵敏度分析 | `sensitivity_analysis` | 多维表格：参数敏感度 |
| 4 | 管道选型 | `NetworkParams` 管网模型 | 设备清单表 |
| 5 | 泵站选型 | `optimize_schedule` 扬程/流量 | 设备选型表 |
| 6 | 安全校核 | `check_odd` 6维安全边界 | 飞书审批：校核流程 |
| 7 | 设计文件 | Report Agent 生成设计说明书 | 飞书审批：四级校审 |
| 8 | 归档 | 自动归档到知识库 | 飞书知识库 |

**测试验证点**：
```python
# D1-T1: 水箱容积优化
from core.design import design_tank, sensitivity_analysis
tank = design_tank(
    q_in_max=500,      # 最大入流 m³/h
    q_out_max=400,     # 最大出流 m³/h
    buffer_time=0.5,   # 缓冲时间 h
    safety_factor=1.2  # 安全系数
)
assert tank["volume"] > 0
assert tank["area"] > 0

# D1-T2: 灵敏度分析确保设计裕度
sa = sensitivity_analysis(
    param_ranges={"area": (0.8, 1.5), "cd": (0.4, 0.8)},
    metric="settling_time"
)
assert all(s["sensitivity"] < 2.0 for s in sa)  # 灵敏度可控

# D1-T3: ODD 安全边界满足设计规范
odd = check_odd({
    "water_level": tank["max_level"],
    "structural_pressure": tank["max_pressure"]
})
assert odd["zone"] in ["green", "yellow"]  # 不得进入红区

# D1-T4: 设计参数在规范范围内
assert 0.5 <= tank["cd"] <= 0.9      # 流量系数规范范围
assert tank["area"] >= 0.3            # 最小截面积
```

#### 案例 O1：运维场景 — 双容水箱日常运行管理

**目标**：日常监控双容水箱运行状态，处理异常

| 步骤 | 活动 | HydroMAS 工具 | 飞书集成 |
|------|------|--------------|---------|
| 1 | 实时监控 | Digital Twin 状态估计 | 飞书机器人：定时推送 |
| 2 | 四预闭环 | ForecastSkill → WarningSkill | 预警通知到飞书群 |
| 3 | 异常诊断 | `detect_leak` + `calc_node_residual` | 飞书卡片：一键诊断 |
| 4 | 维修管理 | — | 飞书审批：维修工单 |
| 5 | 日报生成 | `DailyReportSkill` | 飞书文档：自动日报 |

**测试验证点**：
```python
# O1-T1: 数字孪生状态估计
from core.simulation import DigitalTwinEngine
twin = DigitalTwinEngine(params)
state = twin.update(measurement={"level": 0.8})
assert abs(state.estimated_level - 0.8) < 0.1

# O1-T2: 预警及时触发
from skills import WarningSkill
warning = WarningSkill()
result = warning.execute({"current_level": 0.95, "threshold": 0.9})
assert result.success
assert "warning" in result.data["level"]

# O1-T3: 日报自动生成
from skills import DailyReportSkill
report_skill = DailyReportSkill()
report = report_skill.execute({"date": "2026-02-27"})
assert report.success
assert "水平衡" in report.data.get("content", "")
```

---

### 6.2 氧化铝生产用水系统测试案例

#### 案例 R2：科研场景 — 氧化铝厂蒸发损失优化研究

**目标**：研究冷却塔 + 焙烧 + 赤泥堆场多源蒸发耦合优化

| 步骤 | 活动 | HydroMAS 工具 | 飞书集成 |
|------|------|--------------|---------|
| 1 | 文献调研 | RAGService + 工艺本体 | 飞书知识库：综述 |
| 2 | Merkel 蒸发模型 | `calc_evaporation_merkel` | 模型参数表 |
| 3 | 焙烧蒸发模型 | `calc_calcination_evap` | 参数对比表 |
| 4 | 赤泥蒸发模型 | `calc_red_mud_water` | 多源耦合分析 |
| 5 | 多源耦合优化 | `EvapOptimizationSkill` | 优化结果图表 |
| 6 | 灵敏度分析 | 参数扫描 + 可视化 | 飞书云盘存图 |
| 7 | 论文撰写 | Analysis Agent + Report Agent | 飞书文档协作 |

**测试验证点**：
```python
# R2-T1: Merkel 蒸发模型物理合理性
from core.evaporation import CoolingTowerParams, calc_evaporation_merkel
ct_params = CoolingTowerParams(
    water_flow=1000,    # m³/h
    t_water_in=42,      # °C
    t_water_out=32,     # °C
    t_wet_bulb=28       # °C
)
evap = calc_evaporation_merkel(ct_params)
assert 10 < evap < 30  # 蒸发率 1-3% 合理范围 (m³/h)

# R2-T2: 全厂蒸发总量校核
from skills import EvapOptimizationSkill
evap_skill = EvapOptimizationSkill()
result = evap_skill.execute({})
assert result.success
total = result.data["total_evaporation"]
assert 3000 < total < 5500  # 全厂 ~4200 m³/d

# R2-T3: 优化建议可行性
suggestions = result.data.get("suggestions", [])
assert len(suggestions) > 0
```

#### 案例 D2：设计场景 — 氧化铝厂水网系统设计

**目标**：设计一套日处理 10,400 m³ 的氧化铝厂给排水系统

| 步骤 | 活动 | HydroMAS 工具 | 飞书集成 |
|------|------|--------------|---------|
| 1 | 工艺需求 | `calc_total_process_demand` | 飞书文档：设计任务书 |
| 2 | 水平衡 | `build_balance_graph + calc_full_balance` | 多维表格：节点水量 |
| 3 | 管网设计 | `NetworkParams + simulate_network` | 管网拓扑图 |
| 4 | 冷却塔选型 | `CoolingTowerParams` + Merkel 计算 | 设备比选表 |
| 5 | 回用水设计 | Reuse MCP（质量匹配 + LP优化） | 回用方案表 |
| 6 | 安全分析 | `check_alumina_odd` 12维检查 | 安全评估报告 |
| 7 | 经济评估 | `evaluate_water_kpi` | 投资回报分析 |
| 8 | 设计文件 | Report Agent | 飞书审批：四级校审 |

**测试验证点**：
```python
# D2-T1: 全厂水平衡闭合
from core.water_balance import build_balance_graph, calc_full_balance
graph = build_balance_graph(alumina_config["nodes"], alumina_config["edges"])
balance = calc_full_balance(graph)
assert abs(balance["total_residual"]) < 100  # 残差 <100 m³/d

# D2-T2: 12维 ODD 安全边界校核
from mcp_servers.odd_server import check_alumina_odd
odd = check_alumina_odd(design_params)
for dim in odd["dimensions"]:
    assert dim["zone"] != "red"  # 设计不得进入红区

# D2-T3: 回用水方案经济可行
from mcp_servers.reuse_server import evaluate_reuse_benefit
benefit = evaluate_reuse_benefit(reuse_plan)
assert benefit["reuse_rate"] >= 0.36  # 不低于现状 36%
assert benefit["annual_savings"] > 0   # 有经济效益

# D2-T4: 管网水力计算
from core.simulation import NetworkParams
net = NetworkParams(nodes=12, pipes=15)
sim = simulate_network(net, duration=24)
for node in sim["nodes"]:
    assert node["pressure"] > 0  # 无负压
```

#### 案例 O2：运维场景 — 氧化铝厂水网日常运维

**目标**：保障氧化铝厂水网安全高效运行

| 步骤 | 活动 | HydroMAS 工具 | 飞书集成 |
|------|------|--------------|---------|
| 1 | 每日水平衡 | `DailyReportSkill` | 飞书文档：自动日报 |
| 2 | 泄漏检测 | `LeakDiagnosisSkill` | 飞书告警卡片 |
| 3 | 全局调度 | `GlobalDispatchSkill` | 飞书审批：调度方案 |
| 4 | 蒸发监控 | `EvapOptimizationSkill` | 多维表格：蒸发趋势 |
| 5 | KPI 评估 | `evaluate_water_kpi` | 多维表格：月度 KPI |
| 6 | 维修管理 | — | 飞书工单 + 日历 |

**测试验证点**：
```python
# O2-T1: 泄漏检测端到端
from skills import LeakDiagnosisSkill
leak_skill = LeakDiagnosisSkill()
result = leak_skill.execute({
    "node_data": simulated_leak_data
})
assert result.success
if result.data.get("leak_detected"):
    assert "location" in result.data

# O2-T2: 全局调度方案生成
from skills import GlobalDispatchSkill
dispatch = GlobalDispatchSkill()
result = dispatch.execute({"demand_forecast": forecast_data})
assert result.success
plan = result.data
assert "schedule" in plan

# O2-T3: KPI 指标达标
from mcp_servers.evaluation_server import evaluate_water_kpi
kpi = evaluate_water_kpi(monthly_data)
assert kpi["reuse_rate"] >= 0.36
assert kpi["energy_efficiency"] > 0
```

---

### 6.3 测试案例总览矩阵

| 案例编号 | 系统 | 场景 | 写作 | 建模 | 管理 | 核心验证点 |
|---------|------|------|------|------|------|-----------|
| **R1** | 双容水箱 | 科研 | 论文 | PID/MPC仿真 | 实验管理 | 可复现性、图表自动化 |
| **D1** | 双容水箱 | 设计 | 设计说明书 | 尺寸优化 | 校审流程 | 安全裕度、规范合规 |
| **O1** | 双容水箱 | 运维 | 日报 | 状态估计 | 维修工单 | 实时性、告警准确率 |
| **R2** | 氧化铝 | 科研 | 蒸发论文 | 多源耦合 | 数据管理 | 模型精度、优化效果 |
| **D2** | 氧化铝 | 设计 | 设计文件 | 水网设计 | 质量管控 | 水平衡闭合、安全性 |
| **O2** | 氧化铝 | 运维 | 运行日报 | 泄漏检测 | 调度管理 | 响应速度、节水效果 |

### 6.4 统一验证脚本结构

```
tests/
├── test_scenarios/
│   ├── test_research_tank.py      # R1: 双容水箱科研
│   ├── test_design_tank.py        # D1: 双容水箱设计
│   ├── test_ops_tank.py           # O1: 双容水箱运维
│   ├── test_research_alumina.py   # R2: 氧化铝科研
│   ├── test_design_alumina.py     # D2: 氧化铝设计
│   └── test_ops_alumina.py        # O2: 氧化铝运维
```

每个测试文件验证：
1. **功能正确性**：核心算法输出正确
2. **工作流完整性**：Skill 端到端执行成功
3. **集成一致性**：Agent 调用链路正确
4. **报告可用性**：输出格式符合预期（Markdown/JSON）

---

## 附录：技术选型推荐

### 边缘部署方案

| 层级 | 组件 | 推荐硬件 | 备注 |
|------|------|---------|------|
| 数据存储 | TDengine + Neo4j | 懒猫微服 LC-03 | 7盘位, 96TB |
| AI 推理 | HydroMAS Agents | 懒猫 AI 算力舱 X3 | 275 TOPS, 64GB |
| 前端展示 | FastAPI Web | LC-03 共享 | 低资源占用 |
| 远程访问 | 内网穿透 | 懒猫自带 | 零配置 |

### 研发服务器方案

| 层级 | 组件 | 推荐配置 | 备注 |
|------|------|---------|------|
| 集群调度 | Slurm + K8s | 高校已有 | 统一管理 |
| GPU 训练 | PyTorch + CUDA | A100/H100 | GNN + RL 训练 |
| 数据存储 | BeeGFS/Lustre | 共享存储 | 高带宽并行 IO |
| CI/CD | GitHub Actions | 免费 | 1001 tests 自动化 |

### 协作平台方案

| 功能 | 工具 | 接入方式 |
|------|------|---------|
| 文档协作 | 飞书文档 | 直接使用 |
| 项目管理 | 飞书多维表格 | Webhook 集成 |
| 知识管理 | 飞书知识库 | API 索引 → RAG |
| 即时通讯 | 飞书机器人 | Webhook + 长连接 |
| 审批流程 | 飞书审批 | API 集成 |
| 代码管理 | GitHub | GitHub Actions |
| AI 网关 | Clawdbot/OpenClaw | 自托管 |

---

*文档生成时间：2026-02-27*
*HydroMAS v2.0 — 多智能体智能决策平台*
