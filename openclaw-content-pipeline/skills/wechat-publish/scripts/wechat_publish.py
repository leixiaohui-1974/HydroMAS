#!/usr/bin/env python3
"""
WeChat Official Account Publishing Pipeline
=============================================
从飞书文档导出内容 → 转换为微信公众号文章格式 → 发布为草稿

用法：
  python3 wechat_publish.py <config.json>
  python3 wechat_publish.py --sample

配置文件格式见 generate_sample_config()
"""

import argparse
import json
import os
import re
import sys
import time
import requests
import hashlib

# ── WeChat MP API ──────────────────────────────────────────

WECHAT_BASE = "https://api.weixin.qq.com/cgi-bin"


def wechat_get_token(app_id, app_secret):
    """获取微信公众号 access_token"""
    resp = requests.get(f"{WECHAT_BASE}/token", params={
        "grant_type": "client_credential",
        "appid": app_id,
        "secret": app_secret,
    })
    data = resp.json()
    if "access_token" not in data:
        raise Exception(f"获取微信 access_token 失败: {data}")
    print(f"  [OK] access_token: {data['access_token'][:20]}...")
    return data["access_token"]


def wechat_upload_image(token, image_path):
    """上传图片为永久素材，返回 media_id 和 url"""
    url = f"{WECHAT_BASE}/material/add_material"
    with open(image_path, "rb") as f:
        resp = requests.post(
            url,
            params={"access_token": token, "type": "image"},
            files={"media": (os.path.basename(image_path), f, "image/png")},
        )
    data = resp.json()
    if "media_id" in data:
        print(f"    [OK] 上传图片: {os.path.basename(image_path)} -> {data['media_id']}")
        return data["media_id"], data.get("url", "")
    raise Exception(f"上传图片失败: {data}")


def wechat_upload_thumb(token, image_path):
    """上传封面图为永久素材（thumb 类型）"""
    url = f"{WECHAT_BASE}/material/add_material"
    with open(image_path, "rb") as f:
        resp = requests.post(
            url,
            params={"access_token": token, "type": "thumb"},
            files={"media": (os.path.basename(image_path), f, "image/jpeg")},
        )
    data = resp.json()
    if "media_id" in data:
        print(f"    [OK] 上传封面: {os.path.basename(image_path)} -> {data['media_id']}")
        return data["media_id"]
    raise Exception(f"上传封面失败: {data}")


def wechat_upload_content_image(token, image_path):
    """上传图文消息内的图片，返回可在文章中使用的 URL"""
    url = f"{WECHAT_BASE}/media/uploadimg"
    with open(image_path, "rb") as f:
        resp = requests.post(
            url,
            params={"access_token": token},
            files={"media": (os.path.basename(image_path), f, "image/png")},
        )
    data = resp.json()
    if "url" in data:
        print(f"    [OK] 文章图片: {os.path.basename(image_path)} -> {data['url'][:60]}...")
        return data["url"]
    raise Exception(f"上传文章图片失败: {data}")


def wechat_add_draft(token, articles):
    """创建草稿箱文章"""
    url = f"{WECHAT_BASE}/draft/add"
    resp = requests.post(
        url,
        params={"access_token": token},
        json={"articles": articles},
    )
    data = resp.json()
    if "media_id" in data:
        print(f"  [OK] 草稿创建成功: media_id={data['media_id']}")
        return data["media_id"]
    raise Exception(f"创建草稿失败: {data}")


def wechat_publish(token, media_id):
    """发布草稿（提交审核后自动发布）"""
    url = f"{WECHAT_BASE}/freepublish/submit"
    resp = requests.post(
        url,
        params={"access_token": token},
        json={"media_id": media_id},
    )
    data = resp.json()
    if data.get("errcode", 0) == 0:
        publish_id = data.get("publish_id", "unknown")
        print(f"  [OK] 发布提交成功: publish_id={publish_id}")
        return publish_id
    raise Exception(f"发布失败: {data}")


# ── Feishu API (读取文档) ──────────────────────────────────

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


def feishu_get_doc_content(token, doc_token):
    """获取飞书文档的原始内容（JSON 格式）"""
    resp = requests.get(
        f"{FEISHU_BASE}/docx/v1/documents/{doc_token}/raw_content",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"获取文档内容失败: {data}")
    return data["data"]["content"]


def feishu_get_blocks(token, doc_token, page_token=None):
    """获取飞书文档的所有块"""
    params = {"document_id": doc_token, "page_size": 500}
    if page_token:
        params["page_token"] = page_token
    resp = requests.get(
        f"{FEISHU_BASE}/docx/v1/documents/{doc_token}/blocks",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"获取文档块失败: {data}")
    items = data["data"].get("items", [])
    has_more = data["data"].get("has_more", False)
    next_token = data["data"].get("page_token")
    if has_more and next_token:
        items.extend(feishu_get_blocks(token, doc_token, next_token))
    return items


def feishu_download_image(token, file_token, output_path):
    """下载飞书文档中的图片"""
    resp = requests.get(
        f"{FEISHU_BASE}/drive/v1/medias/{file_token}/download",
        headers={"Authorization": f"Bearer {token}"},
        stream=True,
    )
    if resp.status_code == 200:
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        return True
    return False


# ── Feishu → HTML 转换 ────────────────────────────────────

def blocks_to_html(blocks, feishu_token=None, doc_token=None, wechat_token=None, temp_dir="/tmp"):
    """将飞书文档块转换为微信公众号兼容的 HTML"""
    html_parts = []
    block_map = {b["block_id"]: b for b in blocks}

    for block in blocks:
        bt = block.get("block_type", 0)
        bid = block.get("block_id", "")

        # Page block (document root) - skip
        if bt == 1:
            continue

        # Text block
        elif bt == 2:
            text_html = _rich_text_to_html(block.get("text", {}).get("elements", []))
            if text_html.strip():
                html_parts.append(f'<p style="margin: 1em 0; line-height: 1.8; font-size: 16px; color: #333;">{text_html}</p>')

        # Heading blocks (H1-H9: types 3-11)
        elif 3 <= bt <= 11:
            level = bt - 2  # H1=3, H2=4, ...
            level = min(level, 4)  # 微信最多 h4
            heading_key = {3: "heading1", 4: "heading2", 5: "heading3", 6: "heading4",
                          7: "heading5", 8: "heading6", 9: "heading7", 10: "heading8", 11: "heading9"}
            text_html = _rich_text_to_html(block.get(heading_key.get(bt, "heading1"), {}).get("elements", []))
            sizes = {1: "24px", 2: "20px", 3: "18px", 4: "16px"}
            size = sizes.get(level, "16px")
            html_parts.append(f'<h{level} style="font-size: {size}; font-weight: bold; margin: 1.5em 0 0.5em; color: #1a1a1a;">{text_html}</h{level}>')

        # Bullet list
        elif bt == 12:
            text_html = _rich_text_to_html(block.get("bullet", {}).get("elements", []))
            html_parts.append(f'<p style="margin: 0.3em 0 0.3em 2em; line-height: 1.8; font-size: 16px; color: #333;">&#8226; {text_html}</p>')

        # Ordered list
        elif bt == 13:
            text_html = _rich_text_to_html(block.get("ordered", {}).get("elements", []))
            html_parts.append(f'<p style="margin: 0.3em 0 0.3em 2em; line-height: 1.8; font-size: 16px; color: #333;">{text_html}</p>')

        # Code block
        elif bt == 14:
            text_html = _rich_text_to_html(block.get("code", {}).get("elements", []))
            html_parts.append(f'<pre style="background: #f5f5f5; padding: 1em; border-radius: 4px; overflow-x: auto; font-size: 14px; line-height: 1.6; margin: 1em 0;"><code>{text_html}</code></pre>')

        # Quote block
        elif bt == 15:
            text_html = _rich_text_to_html(block.get("quote", {}).get("elements", []))
            html_parts.append(f'<blockquote style="border-left: 4px solid #ddd; padding: 0.5em 1em; margin: 1em 0; color: #666; font-size: 15px;">{text_html}</blockquote>')

        # Divider
        elif bt == 22:
            html_parts.append('<hr style="border: none; border-top: 1px solid #eee; margin: 1.5em 0;" />')

        # Image block
        elif bt == 27:
            image_data = block.get("image", {})
            file_token = image_data.get("token", "")
            width = image_data.get("width", 800)
            if file_token and feishu_token and wechat_token:
                # 下载飞书图片 → 上传微信
                img_path = os.path.join(temp_dir, f"feishu_img_{bid}.png")
                if feishu_download_image(feishu_token, file_token, img_path):
                    try:
                        wx_url = wechat_upload_content_image(wechat_token, img_path)
                        html_parts.append(f'<p style="text-align: center; margin: 1em 0;"><img src="{wx_url}" style="max-width: 100%;" /></p>')
                    except Exception as e:
                        print(f"    [WARN] 图片上传微信失败: {e}")
                else:
                    print(f"    [WARN] 飞书图片下载失败: {file_token}")

        # Table block (simplified)
        elif bt == 18:
            html_parts.append('<p style="color: #999; font-size: 14px;">[表格内容请查看原文]</p>')

        # Callout block
        elif bt == 19:
            # Get children blocks for callout
            children_ids = block.get("children", [])
            child_html = ""
            for child_id in children_ids:
                child_block = block_map.get(child_id, {})
                child_text = _rich_text_to_html(child_block.get("text", {}).get("elements", []))
                if child_text:
                    child_html += child_text + "<br/>"
            if child_html:
                html_parts.append(f'<div style="background: #f0f7ff; border-left: 4px solid #4a90d9; padding: 1em; margin: 1em 0; border-radius: 4px; font-size: 15px;">{child_html}</div>')

    return "\n".join(html_parts)


def _rich_text_to_html(elements):
    """将飞书富文本元素转为 HTML"""
    parts = []
    for elem in elements:
        if "text_run" in elem:
            text = elem["text_run"].get("content", "")
            style = elem["text_run"].get("text_element_style", {})
            # 转义 HTML
            text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            # 应用样式
            if style.get("bold"):
                text = f"<strong>{text}</strong>"
            if style.get("italic"):
                text = f"<em>{text}</em>"
            if style.get("strikethrough"):
                text = f"<del>{text}</del>"
            if style.get("underline"):
                text = f"<u>{text}</u>"
            if style.get("inline_code"):
                text = f'<code style="background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-size: 14px;">{text}</code>'
            link = style.get("link", {}).get("url", "")
            if link:
                text = f'<a href="{link}" style="color: #576b95;">{text}</a>'
            parts.append(text)
        elif "mention_user" in elem:
            parts.append(elem["mention_user"].get("user_name", "@user"))
        elif "equation" in elem:
            content = elem["equation"].get("content", "")
            parts.append(f'<span style="font-family: serif; font-style: italic;">{content}</span>')
    return "".join(parts)


# ── Pipeline ────────────────────────────────────────────────

def run_pipeline(config):
    """运行飞书→微信公众号发布流水线"""
    wechat = config["wechat"]
    feishu = config.get("feishu", {})
    doc_token = config["doc_token"]
    title = config.get("title", "")
    author = config.get("author", "")
    digest = config.get("digest", "")
    thumb_path = config.get("thumb_image", "")
    auto_publish = config.get("auto_publish", False)

    temp_dir = config.get("temp_dir", "/tmp/wechat-publish")
    os.makedirs(temp_dir, exist_ok=True)

    print("=" * 60)
    print("飞书 → 微信公众号发布流水线")
    print("=" * 60)
    print(f"文档: {doc_token}")
    print(f"标题: {title}")
    print(f"作者: {author}")

    # Step 1: 获取飞书文档
    print("\n[1/5] 获取飞书文档内容...")
    feishu_token = feishu_get_token(feishu["app_id"], feishu["app_secret"])
    blocks = feishu_get_blocks(feishu_token, doc_token)
    print(f"  文档共 {len(blocks)} 个块")

    # 从第一个 heading 提取标题（如果未指定）
    if not title:
        for b in blocks:
            bt = b.get("block_type", 0)
            if 3 <= bt <= 5:
                heading_key = {3: "heading1", 4: "heading2", 5: "heading3"}
                elems = b.get(heading_key.get(bt, "heading1"), {}).get("elements", [])
                for e in elems:
                    if "text_run" in e:
                        title += e["text_run"].get("content", "")
                if title:
                    break
    print(f"  标题: {title}")

    # Step 2: 获取微信 token
    print("\n[2/5] 获取微信公众号 access_token...")
    wx_token = wechat_get_token(wechat["app_id"], wechat["app_secret"])

    # Step 3: 转换为 HTML（包含图片迁移）
    print("\n[3/5] 转换文档为微信公众号 HTML...")
    html_content = blocks_to_html(
        blocks,
        feishu_token=feishu_token,
        doc_token=doc_token,
        wechat_token=wx_token,
        temp_dir=temp_dir,
    )
    print(f"  HTML 长度: {len(html_content)} 字符")

    # 保存 HTML 预览
    preview_path = os.path.join(temp_dir, "preview.html")
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>body {{ max-width: 600px; margin: 0 auto; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }}</style>
</head><body>
<h1 style="font-size: 22px; text-align: center;">{title}</h1>
{html_content}
</body></html>""")
    print(f"  预览: {preview_path}")

    # Step 4: 上传封面图
    print("\n[4/5] 准备封面图...")
    thumb_media_id = ""
    if thumb_path and os.path.exists(thumb_path):
        thumb_media_id = wechat_upload_thumb(wx_token, thumb_path)
    else:
        print("  [SKIP] 无封面图，使用默认")

    # Step 5: 创建草稿
    print("\n[5/5] 创建微信公众号草稿...")
    article = {
        "title": title,
        "author": author,
        "digest": digest or title[:50],
        "content": html_content,
        "content_source_url": f"https://feishu.cn/docx/{doc_token}",
        "need_open_comment": 1,
    }
    if thumb_media_id:
        article["thumb_media_id"] = thumb_media_id

    draft_media_id = wechat_add_draft(wx_token, [article])

    # Optional: 自动发布
    if auto_publish:
        print("\n[bonus] 提交发布...")
        publish_id = wechat_publish(wx_token, draft_media_id)
        print(f"  发布 ID: {publish_id}")

    print("\n" + "=" * 60)
    print("完成!")
    print(f"  草稿 media_id: {draft_media_id}")
    print(f"  预览文件: {preview_path}")
    if not auto_publish:
        print("  提示: 草稿已保存，请在公众号后台预览确认后手动发布")
    print("=" * 60)

    return draft_media_id


def generate_sample_config():
    """生成示例配置"""
    return {
        "feishu": {
            "app_id": "cli_a915cc56d5f89cb1",
            "app_secret": "YOUR_APP_SECRET",
        },
        "wechat": {
            "app_id": "wxec3f615e70666460",
            "app_secret": "YOUR_WECHAT_APP_SECRET",
        },
        "doc_token": "FEISHU_DOC_TOKEN",
        "title": "",
        "author": "CHS水利智慧",
        "digest": "",
        "thumb_image": "",
        "auto_publish": False,
        "temp_dir": "/tmp/wechat-publish",
    }


# ── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="飞书文档 → 微信公众号发布")
    parser.add_argument("config", nargs="?", help="配置文件路径 (JSON)")
    parser.add_argument("--sample", action="store_true", help="输出示例配置")
    parser.add_argument("--publish", action="store_true", help="创建草稿后自动提交发布")
    args = parser.parse_args()

    if args.sample:
        print(json.dumps(generate_sample_config(), indent=2, ensure_ascii=False))
        return

    if not args.config:
        parser.print_help()
        return

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    if args.publish:
        config["auto_publish"] = True

    run_pipeline(config)


if __name__ == "__main__":
    main()
