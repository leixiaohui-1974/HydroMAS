"""ContentPlannerAgent — plans content production pipelines.
内容规划Agent — 规划内容生产流水线。

Analyses a content requirement and produces:
1. Article configuration (topic, style, target audience, keywords)
2. Image plan (number, themes, prompts)
3. Publishing plan (channels, schedule)
4. Video/PPT requirements
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from agents.base_agent import BaseAgent
from agents.message import AgentMessage, MessageType


@dataclass
class ContentRequirement:
    """Parsed content requirement. / 解析后的内容需求。"""

    title: str = ""
    description: str = ""
    content_type: str = "article"  # article, report, tutorial, news
    target_audience: str = "technical"  # technical, general, academic
    channels: list[str] = field(default_factory=list)  # feishu, wechat, video, ppt
    keywords: list[str] = field(default_factory=list)
    priority: str = "normal"  # low, normal, high, urgent
    estimated_length: int = 2000

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "content_type": self.content_type,
            "target_audience": self.target_audience,
            "channels": self.channels,
            "keywords": self.keywords,
            "priority": self.priority,
            "estimated_length": self.estimated_length,
        }


@dataclass
class ContentPlan:
    """Content production plan. / 内容生产计划。"""

    plan_id: str = ""
    requirement: ContentRequirement = field(default_factory=ContentRequirement)
    writing_outline: list[str] = field(default_factory=list)
    image_plan: list[dict] = field(default_factory=list)
    publish_channels: list[str] = field(default_factory=list)
    estimated_stages: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "requirement": self.requirement.to_dict(),
            "writing_outline": self.writing_outline,
            "image_plan": self.image_plan,
            "publish_channels": self.publish_channels,
            "estimated_stages": self.estimated_stages,
            "notes": self.notes,
        }


# Keyword mappings for content type detection
_TYPE_KEYWORDS_ORDERED = [
    ("tutorial", ["教程", "tutorial", "how to", "指南", "guide"]),
    ("report", ["报告", "report", "日报", "周报", "总结"]),
    ("news", ["新闻", "news", "动态", "公告"]),
    ("article", ["文章", "article", "写", "write", "内容"]),
]

_AUDIENCE_KEYWORDS = {
    "technical": ["技术", "工程", "算法", "架构", "AI", "水网", "管网"],
    "general": ["科普", "大众", "入门", "通俗"],
    "academic": ["论文", "学术", "研究", "paper", "journal"],
}

_CHANNEL_KEYWORDS = {
    "feishu": ["飞书", "feishu", "lark"],
    "wechat": ["公众号", "微信", "wechat"],
    "video": ["视频", "video", "讲解"],
    "ppt": ["PPT", "演示", "幻灯片", "presentation"],
}


class ContentPlannerAgent(BaseAgent):
    """Content Planner Agent — analyses requirements and creates plans.
    内容规划Agent — 分析需求并创建计划。
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_capabilities(self) -> list[str]:
        return [
            "requirement_analysis",
            "content_type_detection",
            "audience_targeting",
            "outline_generation",
            "image_planning",
            "channel_selection",
        ]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        action = message.content.get("action", "plan")
        try:
            if action == "analyse_requirement":
                result = self.analyse_requirement(message.content.get("text", ""))
                return message.reply({"result": result.to_dict()})
            elif action == "generate_plan":
                req_data = message.content.get("requirement", {})
                req = ContentRequirement(**req_data)
                result = self.generate_plan(req)
                return message.reply({"result": result.to_dict()})
            else:  # default: plan
                result = self.plan(message.content.get("text", ""))
                return message.reply({"result": result})
        except Exception as exc:
            return message.error_reply(str(exc))

    def analyse_requirement(self, text: str) -> ContentRequirement:
        """Analyse a free-text content requirement.
        分析自由文本内容需求。
        """
        req = ContentRequirement(description=text)

        # Detect content type (check specific types before generic)
        text_lower = text.lower()
        for ctype, keywords in _TYPE_KEYWORDS_ORDERED:
            if any(kw in text_lower for kw in keywords):
                req.content_type = ctype
                break

        # Detect target audience
        for audience, keywords in _AUDIENCE_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                req.target_audience = audience
                break

        # Detect publish channels
        for channel, keywords in _CHANNEL_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                req.channels.append(channel)
        if not req.channels:
            req.channels = ["feishu", "wechat"]  # default

        # Extract keywords (quoted terms or capitalized terms)
        quoted = re.findall(r'["""]([^"""]+)["""]', text)
        req.keywords = quoted[:10]

        # Detect priority
        if any(w in text_lower for w in ["紧急", "urgent", "立即", "immediately"]):
            req.priority = "urgent"
        elif any(w in text_lower for w in ["重要", "important", "优先"]):
            req.priority = "high"

        # Estimate length
        if any(w in text_lower for w in ["长文", "详细", "comprehensive"]):
            req.estimated_length = 5000
        elif any(w in text_lower for w in ["短文", "简要", "brief"]):
            req.estimated_length = 1000

        # Extract title if present
        title_match = re.search(r'[《「]([^》」]+)[》」]', text)
        if title_match:
            req.title = title_match.group(1)

        return req

    def generate_plan(self, req: ContentRequirement) -> ContentPlan:
        """Generate a content production plan from a requirement.
        从需求生成内容生产计划。
        """
        plan = ContentPlan(
            plan_id=f"CP-{uuid.uuid4().hex[:8]}",
            requirement=req,
        )

        # Generate writing outline based on content type
        plan.writing_outline = self._generate_outline(req)

        # Plan images (3-6 per article)
        n_images = min(6, max(3, len(plan.writing_outline) - 1))
        plan.image_plan = [
            {
                "index": i + 1,
                "theme": section,
                "style": "infographic" if req.target_audience == "general"
                else "technical_diagram",
            }
            for i, section in enumerate(plan.writing_outline[:n_images])
        ]

        # Set publish channels
        plan.publish_channels = req.channels.copy()

        # Determine stages
        stages = ["planning", "writing", "review"]
        if plan.image_plan:
            stages.append("illustration")
        if "feishu" in req.channels:
            stages.append("feishu_publish")
        if "wechat" in req.channels:
            stages.append("wechat_publish")
        if "video" in req.channels:
            stages.append("video")
        if "ppt" in req.channels:
            stages.append("ppt")
        plan.estimated_stages = stages

        # Notes
        if req.priority in ("urgent", "high"):
            plan.notes = f"High priority ({req.priority}): expedite review."
        if req.target_audience == "academic":
            plan.notes += " Academic style: include references and citations."

        return plan

    def _generate_outline(self, req: ContentRequirement) -> list[str]:
        """Generate a writing outline based on content type."""
        if req.content_type == "article":
            return [
                "引言 / Introduction",
                "背景与现状 / Background",
                "核心观点 / Core Arguments",
                "技术分析 / Technical Analysis",
                "应用场景 / Applications",
                "总结与展望 / Conclusion",
            ]
        elif req.content_type == "report":
            return [
                "概述 / Overview",
                "数据汇总 / Data Summary",
                "分析与发现 / Analysis",
                "建议 / Recommendations",
                "附录 / Appendix",
            ]
        elif req.content_type == "tutorial":
            return [
                "目标与前提 / Prerequisites",
                "步骤一 / Step 1",
                "步骤二 / Step 2",
                "步骤三 / Step 3",
                "常见问题 / FAQ",
                "总结 / Summary",
            ]
        else:
            return [
                "标题 / Title",
                "正文 / Body",
                "总结 / Summary",
            ]

    def plan(self, text: str) -> dict:
        """End-to-end: analyse + plan. / 端到端：分析+规划。"""
        req = self.analyse_requirement(text)
        plan = self.generate_plan(req)
        return plan.to_dict()
