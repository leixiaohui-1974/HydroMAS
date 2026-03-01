"""Handuo Water Network LLM Agent -- domain-specific AI assistant.
瀚铎水网大模型 Agent -- 领域专用AI助手。

Provides RAG-based Q&A, anomaly causal reasoning, and insight generation
for alumina refinery water network management.  Works in template mode
when no LLM backend (vllm / langchain) is available, using the process
ontology knowledge base (data/process_ontology.json).

v0.2.2: Integrates RAGService for TF-IDF cosine similarity retrieval,
improving recall beyond simple keyword substring matching.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent
from agents.message import AgentMessage, MessageType

logger = logging.getLogger(__name__)

_DEFAULT_KNOWLEDGE_PATH = str(
    Path(__file__).resolve().parent.parent / "data" / "process_ontology.json"
)


class HanduoAgent(BaseAgent):
    """Handuo Water Network domain LLM Agent.
    瀚铎水网大模型 Agent。

    When an LLM backend is available (vllm / langchain), uses it for
    generation.  Otherwise falls back to structured template responses
    built from *process_ontology.json*.

    v0.2.2: Uses RAGService (TF-IDF) for improved knowledge retrieval.
    """

    def __init__(self, knowledge_base_path: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.knowledge_base_path = knowledge_base_path or _DEFAULT_KNOWLEDGE_PATH
        self._knowledge: dict[str, Any] = {}
        self._rag: Any | None = None
        self._llm = None
        self._build_knowledge_index()
        self._build_rag_index()
        self._try_load_llm()

    def get_capabilities(self) -> list[str]:
        return ["domain_qa", "anomaly_diagnosis", "insight_generation", "rag_retrieval"]

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        action = message.content.get("action", "query")
        params = message.content.get("params", {})
        if action == "query":
            result = await self.query(params.get("question", ""), params.get("context"))
        elif action == "diagnose_anomaly":
            result = await self.diagnose_anomaly(
                params.get("anomaly_data", {}), params.get("system_state", {}),
            )
        elif action == "generate_insight":
            text = await self.generate_insight(params.get("data", {}), params.get("report_type", "daily"))
            result = {"insight": text}
        else:
            return message.error_reply(f"Unknown handuo action: {action}")
        return message.reply(result)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def query(self, question: str, context: dict | None = None) -> dict:
        """RAG-based Q&A.  Returns template response when no LLM is loaded.
        基于检索增强生成的问答，无LLM时返回模板响应。

        Args:
            question: Natural-language question / 自然语言问题
            context: Optional context dict / 可选上下文

        Returns:
            Dict with ``answer``, ``sources``, and ``confidence``.
        """
        relevant = self._retrieve(question)

        if self._llm is not None:
            try:
                answer = await self._llm_generate(question, relevant, context)
                return {"answer": answer, "sources": relevant, "confidence": 0.8, "mode": "llm"}
            except Exception as exc:
                logger.warning("LLM generation failed, falling back to template: %s", exc)

        # Template fallback
        answer = self._template_answer(question, relevant, context)
        return {"answer": answer, "sources": relevant, "confidence": 0.5, "mode": "template"}

    async def diagnose_anomaly(self, anomaly_data: dict, system_state: dict) -> dict:
        """Causal reasoning for anomaly diagnosis.
        异常因果推理诊断。

        Args:
            anomaly_data: Description of the anomaly / 异常描述
            system_state: Current system state / 当前系统状态

        Returns:
            Dict with ``diagnosis``, ``possible_causes``, ``recommended_actions``.
        """
        anomaly_type = anomaly_data.get("type", "unknown")
        fault_modes = self._knowledge.get("fault_modes", {})

        # Try to match anomaly to known fault modes
        matched_mode = None
        for mode_key, mode_info in fault_modes.items():
            if anomaly_type in mode_key or mode_key in anomaly_type:
                matched_mode = (mode_key, mode_info)
                break
            # Check effects for fuzzy match
            for effect in mode_info.get("effects", []):
                if effect in anomaly_type or anomaly_type in effect:
                    matched_mode = (mode_key, mode_info)
                    break
            if matched_mode:
                break

        if matched_mode:
            mode_key, mode_info = matched_mode
            causes = mode_info.get("causes", [])
            effects = mode_info.get("effects", [])
            actions = [f"Investigate: {c}" for c in causes]
            return {
                "diagnosis": f"Matched fault mode: {mode_key}",
                "possible_causes": causes,
                "expected_effects": effects,
                "recommended_actions": actions,
                "confidence": 0.7,
                "matched_fault_mode": mode_key,
            }

        # Generic response when no match
        return {
            "diagnosis": f"Anomaly type '{anomaly_type}' not found in knowledge base",
            "possible_causes": ["Unknown -- requires further investigation"],
            "expected_effects": [],
            "recommended_actions": [
                "Check sensor readings for data quality",
                "Review recent maintenance logs",
                "Consult domain expert",
            ],
            "confidence": 0.2,
            "matched_fault_mode": None,
        }

    async def generate_insight(self, data: dict, report_type: str = "daily") -> str:
        """Generate insights from data.
        根据数据生成洞察摘要。

        Args:
            data: Input data dict / 输入数据
            report_type: One of ``"daily"``, ``"weekly"``, ``"anomaly"`` / 报告类型

        Returns:
            Insight text string.
        """
        if self._llm is not None:
            try:
                prompt = self._build_insight_prompt(data, report_type)
                relevant = self._retrieve(report_type)
                return await self._llm_generate(prompt, relevant, data)
            except Exception as exc:
                logger.warning("LLM insight generation failed: %s", exc)

        return self._template_insight(data, report_type)

    # ------------------------------------------------------------------
    # Knowledge index
    # ------------------------------------------------------------------

    def _build_knowledge_index(self) -> None:
        """Build knowledge index from process_ontology.json.
        从工艺本体文件构建知识索引。
        """
        try:
            with open(self.knowledge_base_path, "r", encoding="utf-8") as fh:
                self._knowledge = json.load(fh)
            logger.info(
                "Loaded knowledge base from %s (%d entities, %d fault modes)",
                self.knowledge_base_path,
                len(self._knowledge.get("entities", {})),
                len(self._knowledge.get("fault_modes", {})),
            )
        except FileNotFoundError:
            logger.warning("Knowledge base not found at %s", self.knowledge_base_path)
            self._knowledge = {"entities": {}, "fault_modes": {}}
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON in knowledge base: %s", exc)
            self._knowledge = {"entities": {}, "fault_modes": {}}

    # ------------------------------------------------------------------
    # RAG index (TF-IDF based)
    # ------------------------------------------------------------------

    def _build_rag_index(self) -> None:
        """Build TF-IDF index from knowledge base entities and fault modes.
        从知识库实体和故障模式构建 TF-IDF 索引。
        """
        try:
            from knowledge.rag_service import RAGService
        except ImportError:
            logger.debug("RAGService not available — using keyword-only retrieval")
            return

        docs: list[dict[str, str]] = []

        # Index entities as documents
        for name, info in self._knowledge.get("entities", {}).items():
            cn_name = info.get("cn", "")
            content_parts = [
                f"Entity: {name} ({cn_name})",
                f"Inputs: {', '.join(info.get('inputs', []))}",
                f"Outputs: {', '.join(info.get('outputs', []))}",
                f"Key parameters: {', '.join(info.get('key_params', []))}",
            ]
            docs.append({
                "title": name,
                "content": "\n".join(content_parts),
                "source": "entity",
                "metadata": json.dumps({"type": "entity", "name": name, "cn": cn_name}),
            })

        # Index fault modes as documents
        for name, info in self._knowledge.get("fault_modes", {}).items():
            content_parts = [
                f"Fault mode: {name}",
                f"Causes: {', '.join(info.get('causes', []))}",
                f"Effects: {', '.join(info.get('effects', []))}",
            ]
            docs.append({
                "title": name,
                "content": "\n".join(content_parts),
                "source": "fault_mode",
                "metadata": json.dumps({"type": "fault_mode", "name": name}),
            })

        if docs:
            self._rag = RAGService()
            self._rag.index_documents(docs)
            logger.info("Built RAG index with %d documents", len(docs))

    # ------------------------------------------------------------------
    # LLM integration (optional)
    # ------------------------------------------------------------------

    def _try_load_llm(self) -> None:
        """Attempt to load an LLM backend.  Silently skip if unavailable."""
        try:
            from langchain.llms import BaseLLM  # noqa: F401
            logger.info("langchain available but no model configured -- using template mode")
        except ImportError:
            pass

        try:
            import vllm  # noqa: F401
            logger.info("vllm available but no model configured -- using template mode")
        except ImportError:
            pass

        # LLM remains None -- template mode
        self._llm = None

    async def _llm_generate(self, question: str, sources: list[dict], context: dict | None) -> str:
        """Generate answer using loaded LLM (placeholder for future integration)."""
        raise NotImplementedError("LLM generation not yet configured")

    # ------------------------------------------------------------------
    # Retrieval helpers
    # ------------------------------------------------------------------

    def _retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """Hybrid retrieval: keyword matching + TF-IDF cosine similarity.
        混合检索：关键词匹配 + TF-IDF 余弦相似度。

        Combines exact keyword matches (high precision) with RAGService
        TF-IDF results (better recall for paraphrased queries).
        """
        seen_names: set[str] = set()
        results: list[dict] = []

        # 1. Exact keyword matching (high precision)
        query_lower = query.lower()
        entities = self._knowledge.get("entities", {})
        for name, info in entities.items():
            cn_name = info.get("cn", "")
            if name in query_lower or cn_name in query_lower:
                results.append({"type": "entity", "name": name, "cn": cn_name, **info})
                seen_names.add(name)

        fault_modes = self._knowledge.get("fault_modes", {})
        for name, info in fault_modes.items():
            if name in query_lower:
                results.append({"type": "fault_mode", "name": name, **info})
                seen_names.add(name)
            else:
                for kw in info.get("causes", []) + info.get("effects", []):
                    if kw in query_lower:
                        results.append({"type": "fault_mode", "name": name, **info})
                        seen_names.add(name)
                        break

        # 2. TF-IDF retrieval (better recall for fuzzy/paraphrased queries)
        if self._rag is not None:
            try:
                rag_results = self._rag.query(query, top_k=top_k)
                for r in rag_results:
                    title = r.get("title", "")
                    if title in seen_names:
                        continue  # Already found by keyword matching
                    seen_names.add(title)
                    # Reconstruct the original entity/fault_mode dict
                    source_type = r.get("source", "")
                    if source_type == "entity" and title in entities:
                        info = entities[title]
                        results.append({
                            "type": "entity", "name": title,
                            "cn": info.get("cn", ""), **info,
                            "_rag_score": r.get("score", 0),
                        })
                    elif source_type == "fault_mode" and title in fault_modes:
                        info = fault_modes[title]
                        results.append({
                            "type": "fault_mode", "name": title, **info,
                            "_rag_score": r.get("score", 0),
                        })
            except Exception as exc:
                logger.debug("RAG retrieval failed: %s", exc)

        return results

    # ------------------------------------------------------------------
    # Template fallbacks
    # ------------------------------------------------------------------

    def _template_answer(self, question: str, sources: list[dict], context: dict | None) -> str:
        """Generate a template-based answer when no LLM is available."""
        if not sources:
            return (
                f"No direct knowledge-base match for: '{question}'. "
                "Please refine your query or consult domain documentation."
            )

        lines = [f"Based on knowledge base ({len(sources)} matches):"]
        for src in sources:
            if src["type"] == "entity":
                lines.append(
                    f"- Process '{src['name']}' ({src.get('cn', '')}): "
                    f"inputs={src.get('inputs', [])}, outputs={src.get('outputs', [])}, "
                    f"key_params={src.get('key_params', [])}"
                )
            elif src["type"] == "fault_mode":
                lines.append(
                    f"- Fault mode '{src['name']}': causes={src.get('causes', [])}, "
                    f"effects={src.get('effects', [])}"
                )
        return "\n".join(lines)

    def _template_insight(self, data: dict, report_type: str) -> str:
        """Template-based insight generation."""
        if report_type == "daily":
            intake = data.get("total_intake", 0)
            reuse = data.get("reuse_rate", 0)
            anomalies = data.get("anomalies", [])
            parts = [
                f"Daily summary: total intake {intake:.1f} m3/d, reuse rate {reuse:.1%}.",
            ]
            if anomalies:
                parts.append(f"Detected {len(anomalies)} anomaly(ies) requiring attention.")
            else:
                parts.append("No anomalies detected -- operations normal.")
            return " ".join(parts)

        if report_type == "weekly":
            return (
                f"Weekly trend summary based on {len(data.get('daily_records', []))} days of data. "
                "Consult the detailed report for per-day breakdown."
            )

        if report_type == "anomaly":
            atype = data.get("type", "unknown")
            return (
                f"Anomaly insight: type='{atype}'. "
                "Review causal diagnosis for root-cause analysis."
            )

        return f"Insight for report_type='{report_type}' is not yet templated."

    def _build_insight_prompt(self, data: dict, report_type: str) -> str:
        """Build a prompt string for LLM-based insight generation."""
        return (
            f"Generate a concise {report_type} insight for the following water network data:\n"
            f"{json.dumps(data, ensure_ascii=False, default=str)}"
        )
