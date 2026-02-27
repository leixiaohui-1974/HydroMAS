"""Lightweight RAG (Retrieval-Augmented Generation) service.
轻量级 RAG 检索增强生成服务。

Uses simple TF-IDF keyword matching — no heavy ML dependencies required.
使用简单的 TF-IDF 关键词匹配，无需重量级 ML 依赖。
"""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Any


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase tokens (supports mixed Chinese/English).

    将文本切分为小写词条（支持中英文混合）。
    """
    # Split on whitespace and punctuation, keep Chinese characters as single tokens
    tokens: list[str] = []
    for part in re.split(r"[\s\-_/\\.,;:!?(){}[\]\"']+", text.lower()):
        if not part:
            continue
        # Split Chinese characters individually, keep English words together
        buf = ""
        for ch in part:
            if "\u4e00" <= ch <= "\u9fff":
                if buf:
                    tokens.append(buf)
                    buf = ""
                tokens.append(ch)
            else:
                buf += ch
        if buf:
            tokens.append(buf)
    return tokens


class RAGService:
    """Simple TF-IDF based retrieval service for domain knowledge.

    基于简单 TF-IDF 的领域知识检索服务。

    Parameters
    ----------
    knowledge_dir : str | Path | None
        Directory containing ``.txt`` / ``.md`` knowledge files.
        If *None*, an empty index is created (use :meth:`index_documents`
        to add documents manually).
    """

    def __init__(self, knowledge_dir: str | Path | None = None) -> None:
        self._documents: list[dict[str, Any]] = []
        self._tf: list[dict[str, float]] = []
        self._df: Counter = Counter()
        self._n_docs: int = 0

        if knowledge_dir is not None:
            self._load_directory(Path(knowledge_dir))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def index_documents(self, docs: list[dict[str, str]]) -> None:
        """Index a list of documents.

        索引一组文档。

        Parameters
        ----------
        docs : list[dict]
            Each dict must contain ``"content"`` (text body).
            Optional keys: ``"title"``, ``"source"``, ``"metadata"``.
        """
        for doc in docs:
            self._add_document(doc)
        self._n_docs = len(self._documents)

    def query(self, question: str, top_k: int = 5) -> list[dict]:
        """Retrieve the top-k most relevant documents for a question.

        检索与问题最相关的 top-k 篇文档。

        Parameters
        ----------
        question : str
            The query string.
        top_k : int
            Number of results to return.

        Returns
        -------
        list[dict]
            Each result dict contains ``"content"``, ``"score"``, and any
            metadata from the original document.
        """
        if not self._documents:
            return []

        q_tokens = _tokenize(question)
        if not q_tokens:
            return []

        q_tf = Counter(q_tokens)

        scores: list[tuple[float, int]] = []
        for idx, doc_tf in enumerate(self._tf):
            score = self._cosine_tfidf(q_tf, doc_tf)
            if score > 0:
                scores.append((score, idx))

        scores.sort(key=lambda x: x[0], reverse=True)

        results: list[dict] = []
        for score, idx in scores[:top_k]:
            entry = {**self._documents[idx], "score": round(score, 6)}
            results.append(entry)

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_directory(self, directory: Path) -> None:
        """Load all .txt and .md files from a directory."""
        if not directory.is_dir():
            return
        for fpath in sorted(directory.iterdir()):
            if fpath.suffix in (".txt", ".md"):
                content = fpath.read_text(encoding="utf-8")
                self._add_document({
                    "title": fpath.stem,
                    "content": content,
                    "source": str(fpath),
                })
        self._n_docs = len(self._documents)

    def _add_document(self, doc: dict[str, str]) -> None:
        """Add a single document to the index."""
        content = doc.get("content", "")
        tokens = _tokenize(content)
        if not tokens:
            return

        # Term frequency (normalized)
        tf_raw = Counter(tokens)
        max_freq = max(tf_raw.values())
        tf_norm = {t: c / max_freq for t, c in tf_raw.items()}

        # Update document frequency
        for token in set(tokens):
            self._df[token] += 1

        self._tf.append(tf_norm)
        self._documents.append(doc)

    def _idf(self, term: str) -> float:
        """Inverse document frequency with add-one smoothing."""
        df = self._df.get(term, 0)
        return math.log((self._n_docs + 1) / (df + 1)) + 1

    def _cosine_tfidf(
        self, query_tf: Counter, doc_tf: dict[str, float]
    ) -> float:
        """Compute cosine similarity between query and document TF-IDF vectors."""
        dot = 0.0
        q_norm_sq = 0.0
        d_norm_sq = 0.0

        for term, q_freq in query_tf.items():
            idf = self._idf(term)
            q_w = q_freq * idf
            d_w = doc_tf.get(term, 0.0) * idf
            dot += q_w * d_w
            q_norm_sq += q_w * q_w
            d_norm_sq += d_w * d_w

        # Also account for document terms not in query for d_norm
        for term, d_freq in doc_tf.items():
            if term not in query_tf:
                idf = self._idf(term)
                d_w = d_freq * idf
                d_norm_sq += d_w * d_w

        if q_norm_sq == 0 or d_norm_sq == 0:
            return 0.0

        return dot / (math.sqrt(q_norm_sq) * math.sqrt(d_norm_sq))
