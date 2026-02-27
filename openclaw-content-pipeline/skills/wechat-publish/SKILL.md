---
name: wechat-publish
description: |
  Publish Feishu documents to WeChat Official Account (微信公众号).
  Use when user asks to:
  - publish/push article to WeChat / 公众号
  - send Feishu doc to WeChat official account
  - "发到公众号", "发布到微信公众号", "推送公众号文章"
  - convert Feishu document to WeChat article
homepage: https://mp.weixin.qq.com/
metadata:
  openclaw:
    emoji: "\U0001F4F1"
---

# WeChat Official Account Publisher

Export a Feishu document and publish it as a WeChat Official Account (微信公众号) article.

## Workflow

1. Read Feishu document content (all blocks)
2. Convert to WeChat-compatible HTML (with inline styles)
3. Migrate images: download from Feishu → upload to WeChat
4. Create draft in WeChat Official Account
5. Optionally auto-publish

## Usage

### Step 1: Create config

```json
{
  "feishu": {
    "app_id": "cli_a915cc56d5f89cb1",
    "app_secret": "FROM_CONFIG"
  },
  "wechat": {
    "app_id": "wxec3f615e70666460",
    "app_secret": "FROM_CONFIG"
  },
  "doc_token": "FEISHU_DOC_TOKEN",
  "title": "文章标题（留空自动从文档提取）",
  "author": "作者名",
  "digest": "摘要（留空使用标题前50字）",
  "thumb_image": "/path/to/cover.jpg",
  "auto_publish": false
}
```

### Step 2: Run

```bash
python3 {baseDir}/scripts/wechat_publish.py <config.json>
```

Options:
- `--publish` : 创建草稿后自动提交发布
- `--sample` : 输出示例配置

### Step 3: Preview & Publish

默认只创建草稿，在公众号后台预览确认后手动发布。
也可以传 `--publish` 或设 `auto_publish: true` 自动发布。

## Config Reference

| Field | Required | Description |
|-------|----------|-------------|
| `feishu.app_id` | Yes | 飞书 App ID |
| `feishu.app_secret` | Yes | 飞书 App Secret |
| `wechat.app_id` | Yes | 微信公众号 App ID |
| `wechat.app_secret` | Yes | 微信公众号 App Secret |
| `doc_token` | Yes | 飞书文档 token |
| `title` | No | 文章标题（留空从文档 H1 提取） |
| `author` | No | 作者名 |
| `digest` | No | 摘要 |
| `thumb_image` | No | 封面图路径 |
| `auto_publish` | No | 是否自动发布（默认 false，仅创建草稿） |

## Notes

- 微信公众号文章不支持外链图片，所有图片都会自动从飞书下载后重新上传到微信
- HTML 使用内联样式（微信不支持外部 CSS）
- 复杂表格和数学公式可能需要手动调整
- 建议先创建草稿，在公众号后台预览确认后再发布
- 生成的 HTML 预览文件保存在 temp_dir 中
