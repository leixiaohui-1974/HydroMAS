#!/usr/bin/env python3
"""
Feishu Document Image Pipeline
===============================
通用流程：生成图片（nano-banana-pro）→ 上传飞书 → 插入文档指定位置

用法：
  1. 编辑 pipeline_config.json 配置文件
  2. python3 feishu_image_pipeline.py pipeline_config.json

配置文件格式见 generate_sample_config()
"""

import argparse
import json
import os
import subprocess
import sys
import time
import requests

# ── Feishu API ──────────────────────────────────────────────

FEISHU_BASE = "https://open.feishu.cn/open-apis"


def feishu_get_token(app_id, app_secret):
    """获取飞书 tenant_access_token"""
    resp = requests.post(f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal", json={
        "app_id": app_id,
        "app_secret": app_secret,
    })
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"获取飞书 token 失败: {data}")
    return data["tenant_access_token"]


def feishu_get_children(token, doc_token):
    """获取文档顶层 block 列表"""
    resp = requests.get(
        f"{FEISHU_BASE}/docx/v1/documents/{doc_token}/blocks/{doc_token}",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"获取文档结构失败: {data}")
    return data["data"]["block"]["children"]


def feishu_create_image_block(token, doc_token, index=-1):
    """在文档中创建空图片块"""
    body = {"children": [{"block_type": 27, "image": {}}]}
    if index >= 0:
        body["index"] = index
    resp = requests.post(
        f"{FEISHU_BASE}/docx/v1/documents/{doc_token}/blocks/{doc_token}/children",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"创建图片块失败: {data}")
    return data["data"]["children"][0]["block_id"]


def feishu_upload_image(token, block_id, image_path):
    """上传图片到飞书"""
    with open(image_path, "rb") as f:
        resp = requests.post(
            f"{FEISHU_BASE}/drive/v1/medias/upload_all",
            headers={"Authorization": f"Bearer {token}"},
            data={
                "file_name": os.path.basename(image_path),
                "parent_type": "docx_image",
                "parent_node": block_id,
                "size": str(os.path.getsize(image_path)),
            },
            files={"file": (os.path.basename(image_path), f, "image/png")},
        )
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"上传图片失败: {data}")
    return data["data"]["file_token"]


def feishu_patch_image(token, doc_token, block_id, file_token):
    """用上传的图片填充图片块"""
    resp = requests.patch(
        f"{FEISHU_BASE}/docx/v1/documents/{doc_token}/blocks/{block_id}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"replace_image": {"token": file_token}},
    )
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"填充图片块失败: {data}")


def feishu_delete_block(token, doc_token, block_id):
    """删除文档中的一个块"""
    resp = requests.delete(
        f"{FEISHU_BASE}/docx/v1/documents/{doc_token}/blocks/{block_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    # 飞书 delete 接口可能返回非标准 JSON
    try:
        data = resp.json()
        return data.get("code", -1) == 0
    except Exception:
        return resp.status_code in (200, 204)


# ── Image Generation (nano-banana-pro) ──────────────────────

def generate_image(prompt, output_path, resolution="2K", gemini_api_key=None):
    """用 nano-banana-pro (Gemini 3 Pro Image) 生成图片"""
    script = _find_nano_banana_script()
    if not script:
        raise Exception("找不到 nano-banana-pro 的 generate_image.py 脚本")

    env = os.environ.copy()
    if gemini_api_key:
        env["GEMINI_API_KEY"] = gemini_api_key

    cmd = [
        "uv", "run", script,
        "--prompt", prompt,
        "--filename", output_path,
        "--resolution", resolution,
    ]
    print(f"    执行: uv run generate_image.py --resolution {resolution}")
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=180)

    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        raise Exception(f"图片生成失败 (exit {result.returncode}):\n{stderr or stdout}")

    if not os.path.exists(output_path):
        # 检查是否输出了 MEDIA: 行，里面可能有实际路径
        for line in result.stdout.split("\n"):
            if line.startswith("MEDIA:"):
                actual_path = line.split("MEDIA:", 1)[1].strip()
                if os.path.exists(actual_path):
                    os.rename(actual_path, output_path)
                    break
    if not os.path.exists(output_path):
        raise Exception(f"图片生成后文件不存在: {output_path}\nstdout: {result.stdout[:500]}")

    size_kb = os.path.getsize(output_path) / 1024
    print(f"    生成完成: {output_path} ({size_kb:.0f} KB)")


def _find_nano_banana_script():
    """查找 nano-banana-pro 的生成脚本"""
    import glob
    patterns = [
        os.path.expanduser("~/.local/share/pnpm/global/*/.*openclaw*/node_modules/openclaw/skills/nano-banana-pro/scripts/generate_image.py"),
        "/home/admin/.local/share/pnpm/global/5/.pnpm/openclaw@*/node_modules/openclaw/skills/nano-banana-pro/scripts/generate_image.py",
    ]
    for pat in patterns:
        matches = glob.glob(pat)
        if matches:
            return matches[0]
    return None


# ── Pipeline ────────────────────────────────────────────────

def run_pipeline(config):
    """运行完整流水线"""
    # 解析配置
    feishu = config["feishu"]
    doc_token = config["doc_token"]
    images = config["images"]
    image_dir = config.get("output_dir", "/tmp/feishu-pipeline-images")
    resolution = config.get("resolution", "2K")
    gemini_key = config.get("gemini_api_key", os.environ.get("GEMINI_API_KEY", ""))
    skip_generate = config.get("skip_generate", False)

    os.makedirs(image_dir, exist_ok=True)

    print("=" * 60)
    print("飞书文档图片流水线")
    print("=" * 60)
    print(f"文档: {doc_token}")
    print(f"图片数: {len(images)}")
    print(f"分辨率: {resolution}")
    print(f"输出目录: {image_dir}")
    print(f"跳过生成: {skip_generate}")

    # Step 1: 获取飞书 token
    print("\n[1/4] 获取飞书访问令牌...")
    token = feishu_get_token(feishu["app_id"], feishu["app_secret"])
    print(f"  OK: {token[:20]}...")

    # Step 2: 生成图片
    print(f"\n[2/4] 生成图片 ({len(images)} 张)...")
    for i, img in enumerate(images):
        filename = img["filename"]
        filepath = os.path.join(image_dir, filename)
        img["_filepath"] = filepath

        if skip_generate and os.path.exists(filepath):
            print(f"  [{i+1}/{len(images)}] 跳过 (已存在): {filename}")
            continue

        print(f"  [{i+1}/{len(images)}] 生成: {img.get('description', filename)}")
        try:
            generate_image(img["prompt"], filepath, resolution, gemini_key)
        except Exception as e:
            print(f"    !! 失败: {e}")
            img["_error"] = str(e)
            continue

        time.sleep(1)  # 避免 API 限流

    # Step 3: 获取文档结构并插入图片块
    print(f"\n[3/4] 插入图片到文档...")
    children = feishu_get_children(token, doc_token)
    print(f"  文档当前有 {len(children)} 个顶层块")

    # 从后往前插入以保持索引稳定
    successful = []
    for i, img in enumerate(reversed(images)):
        idx = len(images) - 1 - i
        filepath = img.get("_filepath", "")

        if not os.path.exists(filepath):
            print(f"  [{idx+1}] 跳过 (无文件): {img['filename']}")
            continue

        insert_after = img.get("insert_after_block")
        if not insert_after:
            print(f"  [{idx+1}] 跳过 (无目标位置): {img['filename']}")
            continue

        print(f"  [{idx+1}] {img.get('description', img['filename'])}")

        # 查找插入位置
        block_index = -1
        for j, child_id in enumerate(children):
            if child_id == insert_after:
                block_index = j + 1
                break

        if block_index < 0:
            print(f"    !! 目标块 {insert_after} 不存在，追加到末尾")

        try:
            # 创建图片块
            new_block = feishu_create_image_block(token, doc_token, block_index)
            print(f"    创建块: {new_block}")
            time.sleep(0.5)

            # 上传图片
            file_token = feishu_upload_image(token, new_block, filepath)
            print(f"    上传完成: {file_token}")
            time.sleep(0.3)

            # 填充图片
            feishu_patch_image(token, doc_token, new_block, file_token)
            print(f"    插入完成 ✓")

            img["_block_id"] = new_block
            img["_file_token"] = file_token
            successful.append(img)

            # 刷新 children
            children = feishu_get_children(token, doc_token)
            time.sleep(0.3)

        except Exception as e:
            print(f"    !! 失败: {e}")

    # Step 4: 汇总
    print(f"\n[4/4] 完成")
    print("=" * 60)
    print(f"成功: {len(successful)}/{len(images)} 张图片")
    for img in successful:
        print(f"  ✓ {img.get('description', img['filename'])} -> {img.get('_block_id', '?')}")
    failed = [img for img in images if "_error" in img or "_block_id" not in img]
    if failed:
        print(f"失败: {len(failed)} 张")
        for img in failed:
            print(f"  ✗ {img.get('description', img['filename'])}: {img.get('_error', '未知错误')}")
    print("=" * 60)


def generate_sample_config():
    """生成示例配置文件"""
    return {
        "feishu": {
            "app_id": "cli_a915cc56d5f89cb1",
            "app_secret": "YOUR_APP_SECRET",
        },
        "doc_token": "Hk4md9l25ojaaMxtK6tcumWonRc",
        "gemini_api_key": "YOUR_GEMINI_API_KEY",
        "output_dir": "/home/admin/workspace/workspace/articles/images-new",
        "resolution": "2K",
        "skip_generate": False,
        "images": [
            {
                "filename": "001-web-browser-vs-cli.png",
                "prompt": "Clean infographic comparing web browser AI chat vs command-line terminal AI tool...",
                "insert_after_block": "doxcnS6BbSUg8BkrTOfBNOex5Hf",
                "description": "网页浏览器 vs 命令行终端对比图",
            },
        ],
    }


# ── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="飞书文档图片流水线")
    parser.add_argument("config", nargs="?", help="配置文件路径 (JSON)")
    parser.add_argument("--sample", action="store_true", help="输出示例配置文件")
    parser.add_argument("--skip-generate", action="store_true", help="跳过图片生成（使用已有图片）")
    args = parser.parse_args()

    if args.sample:
        print(json.dumps(generate_sample_config(), indent=2, ensure_ascii=False))
        return

    if not args.config:
        parser.print_help()
        return

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    if args.skip_generate:
        config["skip_generate"] = True

    run_pipeline(config)


if __name__ == "__main__":
    main()
