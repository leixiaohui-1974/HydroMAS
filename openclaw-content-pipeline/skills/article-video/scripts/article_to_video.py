#!/usr/bin/env python3
"""
Article-to-Video Pipeline
==========================
将飞书文章转换为带旁白的视频（类似 NotebookLM 风格）

流程：文章分段 → TTS语音(并发) → 配图片(预缩放) → FFmpeg合成视频

用法：
  python3 article_to_video.py <config.json>
  python3 article_to_video.py --sample

依赖：
  pip install edge-tts Pillow
  brew install ffmpeg  (或 apt install ffmpeg)
"""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import textwrap
import time


# ── TTS (Edge TTS - 免费、质量好) ─────────────────────────

async def generate_tts(text, output_path, voice="zh-CN-YunxiNeural", rate="+0%"):
    """用 Edge TTS 生成语音"""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_path)
    return output_path


async def generate_tts_safe(index, text, output_path, voice, rate):
    """带错误处理的 TTS，返回 (index, path_or_None, error_or_None)"""
    try:
        await generate_tts(text, output_path, voice, rate)
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 100:
            return (index, None, "文件为空或不存在")
        return (index, output_path, None)
    except Exception as e:
        return (index, None, str(e))


async def generate_all_tts(tasks, voice, rate):
    """并发生成所有 TTS"""
    coros = [
        generate_tts_safe(i, text, path, voice, rate)
        for i, text, path in tasks
    ]
    return await asyncio.gather(*coros)


def get_audio_duration(path):
    """获取音频时长（秒）"""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())


# ── 文章分段 ───────────────────────────────────────────────

def split_article_to_segments(article_text):
    """将文章按段落分割为语音段"""
    segments = []
    lines = article_text.strip().split("\n")
    current_segment = {"title": "", "text": "", "type": "content"}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 跳过元数据行
        if line.startswith("---") or line.startswith("*作者") or line.startswith("*本文基于"):
            continue

        # 标题行 → 新段
        if line.startswith("# "):
            if current_segment["text"]:
                segments.append(current_segment)
            current_segment = {"title": line[2:].strip(), "text": "", "type": "title"}
            continue

        if line.startswith("## "):
            if current_segment["text"]:
                segments.append(current_segment)
            title = line[3:].strip()
            current_segment = {"title": title, "text": "", "type": "section"}
            continue

        if line.startswith("### "):
            if current_segment["text"]:
                segments.append(current_segment)
            title = line[4:].strip()
            current_segment = {"title": title, "text": "", "type": "subsection"}
            continue

        # 引用行
        if line.startswith("> "):
            line = line[2:]

        # 列表项
        if line.startswith("- "):
            line = line[2:]
        if re.match(r"^\d+\. ", line):
            line = re.sub(r"^\d+\. ", "", line)

        # 跳过代码块和表格
        if line.startswith("```") or line.startswith("|"):
            continue

        # 清理 markdown 格式
        line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)  # bold
        line = re.sub(r"\*(.*?)\*", r"\1", line)  # italic
        line = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", line)  # links

        if line:
            current_segment["text"] += line + "。" if not line.endswith(("。", "！", "？", "…", "：")) else line + " "

    if current_segment["text"]:
        segments.append(current_segment)

    # 合并过短的段落
    merged = []
    for seg in segments:
        seg["text"] = seg["text"].strip()
        if not seg["text"]:
            continue
        if merged and len(seg["text"]) < 30 and seg["type"] == "content":
            merged[-1]["text"] += " " + seg["text"]
        else:
            merged.append(seg)

    return merged


# ── 图片准备 ──────────────────────────────────────────────

def create_title_card(text, output_path, width=1920, height=1080):
    """用 FFmpeg 创建纯色背景 + 文字的标题卡"""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i",
        f"color=c=#1a1a2e:s={width}x{height}:d=1",
        "-vframes", "1",
        output_path
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path


def create_text_overlay_image(text, subtitle, output_path, width=1920, height=1080):
    """创建带文字覆盖的图片（用 Python PIL 或 FFmpeg）"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (width, height), color=(26, 26, 46))
        draw = ImageDraw.Draw(img)

        # 尝试加载中文字体
        font_paths = [
            "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/System/Library/Fonts/PingFang.ttc",
        ]
        font_large = None
        font_small = None
        for fp in font_paths:
            if os.path.exists(fp):
                font_large = ImageFont.truetype(fp, 60)
                font_small = ImageFont.truetype(fp, 32)
                break
        if not font_large:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # 绘制标题
        lines = textwrap.wrap(text, width=20)
        y = height // 3
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font_large)
            w = bbox[2] - bbox[0]
            draw.text(((width - w) / 2, y), line, fill=(255, 255, 255), font=font_large)
            y += 80

        # 绘制副标题
        if subtitle:
            sub_lines = textwrap.wrap(subtitle, width=35)
            y += 40
            for line in sub_lines:
                bbox = draw.textbbox((0, 0), line, font=font_small)
                w = bbox[2] - bbox[0]
                draw.text(((width - w) / 2, y), line, fill=(180, 180, 200), font=font_small)
                y += 50

        img.save(output_path)
        return output_path

    except ImportError:
        return create_title_card(text, output_path, width, height)


def prescale_image(src_path, dst_path, width=1920, height=1080):
    """预缩放图片到目标分辨率，居中填充黑边"""
    try:
        from PIL import Image
        img = Image.open(src_path)
        if img.size == (width, height):
            # 已经是目标尺寸，直接复制
            if src_path != dst_path:
                img.save(dst_path)
            return dst_path

        # 计算缩放比例（保持比例，fit inside）
        ratio = min(width / img.width, height / img.height)
        new_w = int(img.width * ratio)
        new_h = int(img.height * ratio)
        resized = img.resize((new_w, new_h), Image.LANCZOS)

        # 居中粘贴到黑色背景
        canvas = Image.new("RGB", (width, height), (0, 0, 0))
        offset_x = (width - new_w) // 2
        offset_y = (height - new_h) // 2
        canvas.paste(resized, (offset_x, offset_y))
        canvas.save(dst_path, quality=95)
        return dst_path

    except ImportError:
        # 没有 PIL，用 FFmpeg 缩放
        cmd = [
            "ffmpeg", "-y", "-i", src_path,
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black",
            "-frames:v", "1",
            dst_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return dst_path


# ── FFmpeg 视频合成 ────────────────────────────────────────

# 统一编码参数，确保 concat -c copy 兼容
VIDEO_CODEC_ARGS = [
    "-c:v", "libx264",
    "-preset", "fast",
    "-tune", "stillimage",
    "-profile:v", "high",
    "-level", "4.1",
    "-pix_fmt", "yuv420p",
    "-r", "25",
]
AUDIO_CODEC_ARGS = [
    "-c:a", "aac",
    "-b:a", "128k",
    "-ar", "44100",
    "-ac", "2",
]


def create_segment_video(image_path, audio_path, output_path, fade_duration=0.5):
    """将一张预缩放的图片 + 一段音频合成为视频片段"""
    duration = get_audio_duration(audio_path)

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", image_path,
        "-i", audio_path,
        *VIDEO_CODEC_ARGS,
        *AUDIO_CODEC_ARGS,
        "-vf", f"fade=in:0:{int(fade_duration * 25)},fade=out:st={max(0, duration - fade_duration)}:d={fade_duration}",
        "-t", str(duration + 0.5),
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"FFmpeg segment 失败: {result.stderr[-500:]}")
    return output_path


def concat_videos(segment_paths, output_path):
    """将多段视频拼接为一个（流复制，不重新编码）"""
    list_file = output_path + ".txt"
    with open(list_file, "w") as f:
        for p in segment_paths:
            f.write(f"file '{p}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        "-movflags", "+faststart",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    os.remove(list_file)
    if result.returncode != 0:
        raise Exception(f"FFmpeg concat 失败: {result.stderr[-500:]}")
    return output_path


# ── Pipeline ────────────────────────────────────────────────

def run_pipeline(config):
    """运行文章→视频流水线"""
    article_path = config.get("article_path", "")
    article_text = config.get("article_text", "")
    images_dir = config.get("images_dir", "")
    image_files = config.get("images", [])
    output_path = config.get("output", "/tmp/article-video/output.mp4")
    voice = config.get("voice", "zh-CN-YunxiNeural")
    rate = config.get("rate", "+0%")
    title = config.get("title", "")

    temp_dir = config.get("temp_dir", "/tmp/article-video")
    os.makedirs(temp_dir, exist_ok=True)

    # 读取文章
    if article_path and os.path.exists(article_path):
        with open(article_path, "r", encoding="utf-8") as f:
            article_text = f.read()
    if not article_text:
        raise Exception("无文章内容")

    pipeline_start = time.time()
    print("=" * 60)
    print("文章 → 视频 Pipeline (优化版)")
    print("=" * 60)

    # Step 1: 分段
    print("\n[1/4] 分割文章...")
    segments = split_article_to_segments(article_text)
    print(f"  共 {len(segments)} 个段落")
    for i, seg in enumerate(segments):
        print(f"  [{i+1}] {seg['type']}: {seg['title'] or seg['text'][:40]}...")

    # Step 2: TTS (并发)
    print(f"\n[2/4] 并发生成语音 (voice={voice}, {len(segments)} 段)...")
    tts_start = time.time()

    tts_tasks = []
    for i, seg in enumerate(segments):
        audio_path = os.path.join(temp_dir, f"seg_{i:03d}.mp3")
        tts_text = seg["text"]
        if seg["title"] and seg["type"] in ("title", "section"):
            tts_text = seg["title"] + "。" + tts_text
        tts_tasks.append((i, tts_text, audio_path))

    results = asyncio.run(generate_all_tts(tts_tasks, voice, rate))

    audio_files = [None] * len(segments)
    ok_count = 0
    for idx, path, err in results:
        if path:
            audio_files[idx] = path
            duration = get_audio_duration(path)
            print(f"  [{idx+1}/{len(segments)}] OK ({duration:.1f}s)")
            ok_count += 1
        else:
            print(f"  [{idx+1}/{len(segments)}] FAIL: {err}")

    tts_elapsed = time.time() - tts_start
    print(f"  TTS 完成: {ok_count}/{len(segments)} 成功, 耗时 {tts_elapsed:.1f}s")

    # Step 3: 准备图片（匹配段落 + 预缩放）
    print(f"\n[3/4] 准备图片 (预缩放到 1920x1080)...")
    img_start = time.time()

    available_images = []
    if images_dir:
        for f in sorted(os.listdir(images_dir)):
            if f.endswith((".png", ".jpg", ".jpeg")):
                available_images.append(os.path.join(images_dir, f))
    for img in image_files:
        if os.path.exists(img):
            available_images.append(img)
    print(f"  可用图片: {len(available_images)} 张")

    # 预缩放所有外部图片
    prescaled_dir = os.path.join(temp_dir, "prescaled")
    os.makedirs(prescaled_dir, exist_ok=True)
    prescaled_images = []
    for img_path in available_images:
        dst = os.path.join(prescaled_dir, os.path.basename(img_path))
        if not os.path.exists(dst):
            prescale_image(img_path, dst)
        prescaled_images.append(dst)

    if prescaled_images:
        orig_size = sum(os.path.getsize(p) for p in available_images) / (1024 * 1024)
        new_size = sum(os.path.getsize(p) for p in prescaled_images) / (1024 * 1024)
        print(f"  预缩放: {orig_size:.1f}MB → {new_size:.1f}MB")

    # 分配图片给段落
    segment_images = []
    img_idx = 0
    for i, seg in enumerate(segments):
        if seg["type"] in ("title", "section", "subsection"):
            img_path = os.path.join(temp_dir, f"card_{i:03d}.png")
            subtitle = seg["text"][:80] if seg["text"] else ""
            create_text_overlay_image(seg["title"], subtitle, img_path)
            segment_images.append(img_path)
        elif img_idx < len(prescaled_images):
            segment_images.append(prescaled_images[img_idx])
            img_idx += 1
        else:
            if prescaled_images:
                segment_images.append(prescaled_images[img_idx % len(prescaled_images)])
                img_idx += 1
            else:
                img_path = os.path.join(temp_dir, f"card_{i:03d}.png")
                create_text_overlay_image("", seg["text"][:60], img_path)
                segment_images.append(img_path)

    img_elapsed = time.time() - img_start
    print(f"  图片准备完成, 耗时 {img_elapsed:.1f}s")

    # Step 4: 合成视频
    print(f"\n[4/4] 合成视频...")
    encode_start = time.time()

    segment_videos = []
    for i, (audio, image) in enumerate(zip(audio_files, segment_images)):
        if audio is None:
            continue
        seg_video = os.path.join(temp_dir, f"video_{i:03d}.mp4")
        print(f"  [{i+1}/{len(audio_files)}] 编码片段...", end=" ", flush=True)
        seg_start = time.time()
        try:
            create_segment_video(image, audio, seg_video)
            seg_elapsed = time.time() - seg_start
            print(f"OK ({seg_elapsed:.1f}s)")
            segment_videos.append(seg_video)
        except Exception as e:
            print(f"FAIL: {e}")

    if not segment_videos:
        raise Exception("没有成功生成任何视频片段")

    encode_elapsed = time.time() - encode_start
    print(f"  编码完成: {len(segment_videos)} 段, 耗时 {encode_elapsed:.1f}s")

    # 拼接（流复制）
    print(f"\n  拼接 {len(segment_videos)} 个片段 (流复制)...")
    concat_start = time.time()
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    concat_videos(segment_videos, output_path)
    concat_elapsed = time.time() - concat_start
    print(f"  拼接完成, 耗时 {concat_elapsed:.1f}s")

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    total_duration = sum(get_audio_duration(a) for a in audio_files if a)
    total_elapsed = time.time() - pipeline_start

    print(f"\n{'='*60}")
    print(f"完成!")
    print(f"  输出: {output_path}")
    print(f"  大小: {size_mb:.1f} MB")
    print(f"  时长: {total_duration:.0f} 秒 ({total_duration/60:.1f} 分钟)")
    print(f"  片段: {len(segment_videos)}")
    print(f"  总耗时: {total_elapsed:.1f}s")
    print(f"    TTS: {tts_elapsed:.1f}s | 编码: {encode_elapsed:.1f}s | 拼接: {concat_elapsed:.1f}s")
    print(f"{'='*60}")

    return output_path


def generate_sample_config():
    """生成示例配置"""
    return {
        "article_path": "/home/admin/workspace/workspace/articles/water-ai-cowork-article.md",
        "images_dir": "/home/admin/workspace/workspace/articles/images-new",
        "images": [],
        "output": "/home/admin/workspace/workspace/articles/video/article-002.mp4",
        "voice": "zh-CN-YunxiNeural",
        "rate": "+0%",
        "title": "从 AI 助手到水网大脑：同一条进化路",
        "temp_dir": "/tmp/article-video",
    }


# ── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="文章 → 视频 Pipeline")
    parser.add_argument("config", nargs="?", help="配置文件路径 (JSON)")
    parser.add_argument("--sample", action="store_true", help="输出示例配置")
    args = parser.parse_args()

    if args.sample:
        print(json.dumps(generate_sample_config(), indent=2, ensure_ascii=False))
        return

    if not args.config:
        parser.print_help()
        return

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    run_pipeline(config)


if __name__ == "__main__":
    main()
