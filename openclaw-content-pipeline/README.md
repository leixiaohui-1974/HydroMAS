# OpenClaw 全栈内容生产流水线

基于 OpenClaw + 飞书的 AI 内容生产系统，一条龙完成：**写文章 → AI配图 → 插入飞书文档 → 发公众号 → 生成视频**。

## 目录结构

```
openclaw-content-pipeline/
├── AGENT.md                          # 主控 Agent 提示词（v4，6个技能）
├── README.md
├── skills/
│   ├── article-video/                # 文章转视频（优化版）
│   │   ├── SKILL.md
│   │   └── scripts/article_to_video.py
│   ├── feishu-image-pipeline/        # AI配图 + 飞书文档插入
│   │   ├── SKILL.md
│   │   └── scripts/feishu_image_pipeline.py
│   └── wechat-publish/              # 飞书文档 → 微信公众号
│       ├── SKILL.md
│       └── scripts/wechat_publish.py
├── configs/                          # Pipeline 配置文件
│   ├── pipeline_001_cli_article.json
│   ├── pipeline_002_water_ai_article.json
│   ├── video_001_cli_article.json
│   └── video_002_water_ai.json
└── articles/                         # 文章 Markdown 源文件
    ├── ai-cli-article-draft.md
    └── water-ai-cowork-article.md
```

## 技能说明

### 1. article-video — 文章转视频
- 文章按标题自动分段 → Edge TTS 并发生成语音 → 配图匹配 → FFmpeg 合成 1080p MP4
- 优化点：TTS 并发（37x）、FFmpeg 死锁修复、concat 流复制（37x）、图片预缩放
- 依赖：`edge-tts`, `Pillow`, `ffmpeg`

### 2. feishu-image-pipeline — AI 配图
- 用 nano-banana-pro (Gemini 3 Pro Image) 生成中文标签配图
- 4 步流程：创建图片块 → 上传图片 → patch 填充 → 刷新文档结构
- 依赖：`requests`, nano-banana-pro

### 3. wechat-publish — 微信公众号发布
- 飞书文档 → 提取内容和图片 → 上传微信 → 创建草稿/发布
- 自动处理图片迁移（飞书 → 微信素材库）

## 运行环境

- 服务器：阿里云 ECS（建议 4核 8GB）
- 平台：OpenClaw 2026.2.21-2
- 飞书机器人：已配置 doc/drive/im 权限
- 模型：DashScope qwen3.5-plus / DeepSeek V3.2 / Gemini 3 Flash
