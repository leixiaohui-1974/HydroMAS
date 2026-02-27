---
name: article-video
description: |
  Convert articles to narrated videos (NotebookLM-style). Use when user asks to:
  - create video from article
  - generate narrated video / podcast video
  - "文章转视频", "生成讲解视频", "做个视频"
homepage: https://github.com/rany2/edge-tts
metadata:
  openclaw:
    emoji: "\U0001F3AC"
    requires:
      bins: [ffmpeg, python3]
      env: []
---

# Article to Video Pipeline

Convert a Feishu article into a narrated video with images, similar to NotebookLM's video feature.

## Workflow

1. Split article into segments by sections
2. Generate TTS narration for each segment (Edge TTS, free, high quality Chinese voices)
3. Match images to segments (use article images + auto-generated title cards)
4. Combine with FFmpeg into final MP4

## Usage

### Create config

```json
{
  "article_path": "/path/to/article.md",
  "images_dir": "/path/to/images/",
  "output": "/path/to/output.mp4",
  "voice": "zh-CN-YunxiNeural",
  "rate": "+0%",
  "title": "Article Title"
}
```

### Run

```bash
python3 {baseDir}/scripts/article_to_video.py <config.json>
```

## Available Chinese Voices

| Voice | Gender | Style |
|-------|--------|-------|
| zh-CN-YunxiNeural | Male | Standard narrator |
| zh-CN-YunyangNeural | Male | Professional news |
| zh-CN-XiaoxiaoNeural | Female | Warm conversational |
| zh-CN-XiaoyiNeural | Female | Young energetic |

## Notes

- Edge TTS is free, no API key needed
- FFmpeg required for video synthesis
- Output is 1080p MP4 with AAC audio
- Article images are auto-scaled and padded to 16:9
- Title cards auto-generated for section headings
