---
name: feishu-image-pipeline
description: |
  Generate AI images and insert them into Feishu documents. Use when user asks to:
  - add/insert/generate images for a Feishu article or document
  - run image pipeline for an article
  - batch generate illustrations and upload to Feishu
  - "给文章生成图片", "插入配图", "图片pipeline"
homepage: https://open.feishu.cn/
metadata:
  openclaw:
    emoji: "\U0001F5BC"
    requires:
      bins: [uv, python3]
      env: [GEMINI_API_KEY]
    primaryEnv: GEMINI_API_KEY
---

# Feishu Image Pipeline

Batch-generate AI images (via Gemini 3 Pro Image / nano-banana-pro) and insert them into Feishu documents at specified positions.

## Workflow

1. **Prepare config** - Create a JSON config file specifying document token, images (filename, prompt, insert position)
2. **Run pipeline** - Execute the pipeline script
3. **Grant permissions** - Use `feishu_perm` tool to grant user edit access

## Usage

### Step 1: Create pipeline config

Create a JSON file (e.g., `pipeline_002.json`) with this structure:

```json
{
  "feishu": {
    "app_id": "cli_a915cc56d5f89cb1",
    "app_secret": "FROM_ENV_OR_CONFIG"
  },
  "doc_token": "FEISHU_DOC_TOKEN",
  "gemini_api_key": "FROM_ENV",
  "output_dir": "/home/admin/workspace/workspace/articles/images-new",
  "resolution": "2K",
  "skip_generate": false,
  "images": [
    {
      "filename": "002-image-name.png",
      "prompt": "Detailed image description for AI generation...",
      "insert_after_block": "doxcnXXXXX",
      "description": "Human-readable image description"
    }
  ]
}
```

### Step 2: Find document block IDs

Use `feishu_doc` tool to read the document structure and find the block IDs where images should be inserted after:

```
feishu_doc read <doc_token>
```

### Step 3: Run the pipeline

```bash
python3 {baseDir}/scripts/feishu_image_pipeline.py <config.json>
```

Options:
- `--skip-generate` : Skip image generation, use existing image files
- `--sample` : Output a sample config file

### Step 4: Grant permissions (optional)

After pipeline completes, use `feishu_perm` to grant the user edit access:
- Action: `add`
- Token: the doc_token
- Type: `docx`
- Permission: `edit` or `full_access`

## Config Reference

| Field | Required | Description |
|-------|----------|-------------|
| `feishu.app_id` | Yes | Feishu app ID |
| `feishu.app_secret` | Yes | Feishu app secret |
| `doc_token` | Yes | Target document token (from URL) |
| `gemini_api_key` | No | Gemini API key (or set GEMINI_API_KEY env) |
| `output_dir` | No | Image output directory (default: /tmp/feishu-pipeline-images) |
| `resolution` | No | Image resolution: 1K, 2K, 4K (default: 2K) |
| `skip_generate` | No | Skip generation, use existing files (default: false) |
| `images[].filename` | Yes | Output image filename |
| `images[].prompt` | Yes | AI image generation prompt (English recommended) |
| `images[].insert_after_block` | Yes | Block ID to insert image after |
| `images[].description` | No | Human-readable description |

## Notes

- Image prompt 主体用英文描述构图，但所有文字标签必须用中文（如 `labeled '网页聊天' in Chinese`），结尾加 `All text labels must be in Chinese.`
- Use 2K resolution for good quality/size balance
- Pipeline processes images in reverse order to preserve insertion indices
- The script auto-detects nano-banana-pro's generate_image.py location
- Each image takes ~10-30 seconds to generate
