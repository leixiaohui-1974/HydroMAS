#!/usr/bin/env python3
"""HydroMAS query script for OpenClaw skill integration.
OpenClaw 技能脚本 — 调用 HydroMAS 网关 API。

Usage:
    python3 hydromas_query.py chat "检查今天水平衡" --role operator
    python3 hydromas_query.py skill daily_report --params '{"date": "2026-02-28"}'
    python3 hydromas_query.py roles
    python3 hydromas_query.py skills --role operator
    python3 hydromas_query.py health
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import urllib.error

BASE_URL = os.environ.get("HYDROMAS_URL", "http://localhost:8000")
TIMEOUT = 60


def _post(path: str, body: dict) -> dict:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(path: str) -> dict:
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def cmd_chat(args):
    result = _post("/api/gateway/chat", {
        "message": args.message,
        "role": args.role,
        "session_id": args.session or "",
    })
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_skill(args):
    params = json.loads(args.params) if args.params else {}
    result = _post("/api/gateway/skill", {
        "skill_name": args.skill_name,
        "params": params,
    })
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_roles(args):
    result = _get("/api/gateway/roles")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_skills(args):
    path = "/api/gateway/skills"
    if args.role:
        path += f"?role={args.role}"
    result = _get(path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_health(args):
    result = _get("/api/gateway/health")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="HydroMAS query tool for OpenClaw")
    sub = parser.add_subparsers(dest="command", required=True)

    p_chat = sub.add_parser("chat", help="Send natural language message")
    p_chat.add_argument("message", help="User message text")
    p_chat.add_argument("--role", default="operator", choices=["researcher", "designer", "operator"])
    p_chat.add_argument("--session", default="", help="Session ID")
    p_chat.set_defaults(func=cmd_chat)

    p_skill = sub.add_parser("skill", help="Execute a named skill")
    p_skill.add_argument("skill_name", help="Skill name")
    p_skill.add_argument("--params", default="{}", help="JSON params")
    p_skill.set_defaults(func=cmd_skill)

    p_roles = sub.add_parser("roles", help="List available roles")
    p_roles.set_defaults(func=cmd_roles)

    p_skills = sub.add_parser("skills", help="List available skills")
    p_skills.add_argument("--role", default="", help="Filter by role")
    p_skills.set_defaults(func=cmd_skills)

    p_health = sub.add_parser("health", help="Health check")
    p_health.set_defaults(func=cmd_health)

    args = parser.parse_args()
    try:
        args.func(args)
    except urllib.error.URLError as exc:
        print(f"ERROR: Cannot connect to HydroMAS at {BASE_URL}: {exc.reason}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
