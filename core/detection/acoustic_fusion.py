"""Acoustic-hydraulic fusion — combine acoustic sensor events with hydraulic anomaly data.
声学-水力融合 — 将声学传感器事件与水力异常数据相结合。

Fuses two independent evidence streams (acoustic leak signatures and
GNN-based hydraulic anomaly scores) to produce high-confidence leak
localization results.
融合两个独立证据流（声学泄漏特征和基于 GNN 的水力异常分数）以产生
高置信度泄漏定位结果。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AcousticEvent:
    """A single acoustic leak-signature event. / 单次声学泄漏特征事件。"""

    sensor_id: str = ""            # Sensor identifier / 传感器标识
    timestamp: float = 0.0        # Event timestamp (s) / 事件时间戳
    amplitude_db: float = 0.0     # Signal amplitude (dB) / 信号幅值
    frequency_hz: float = 0.0     # Dominant frequency (Hz) / 主频率
    pipe_segment: str = ""        # Associated pipe segment ID / 关联管段标识

    def validate(self) -> None:
        """Validate parameter ranges. / 验证参数范围。"""
        if self.amplitude_db < 0:
            raise ValueError(
                f"Amplitude must be >= 0 dB, got {self.amplitude_db}"
            )
        if self.frequency_hz < 0:
            raise ValueError(
                f"Frequency must be >= 0 Hz, got {self.frequency_hz}"
            )


def fuse_acoustic_hydraulic(
    acoustic_events: list[AcousticEvent],
    hydraulic_suspects: list[dict],
) -> list[dict]:
    """Fuse acoustic events with hydraulic anomaly suspects.
    将声学事件与水力异常嫌疑管段融合。

    Combines two independent evidence streams:
      1. Acoustic events localised to pipe segments.
      2. Hydraulic suspects produced by GNN anomaly detection
         (each dict must have at least 'pipe_id' and 'confidence').

    The combined confidence is computed via a weighted Bayesian-style
    update:  ``combined = 1 - (1 - p_h) * (1 - p_a)``  where *p_h*
    is the hydraulic confidence and *p_a* is derived from the acoustic
    amplitude.

    Args:
        acoustic_events: List of ``AcousticEvent`` instances.
                         ``AcousticEvent`` 实例列表。
        hydraulic_suspects: List of dicts from ``localize_leak``, each with
                            'pipe_id' and 'confidence'.
                            由 ``localize_leak`` 产生的字典列表。

    Returns:
        List of dicts, each with pipe_id, combined_confidence, and
        evidence list describing contributing sources.
        字典列表，每个包含 pipe_id、combined_confidence 和 evidence 来源列表。
    """
    # Validate acoustic events
    for evt in acoustic_events:
        evt.validate()

    # Index hydraulic suspects by pipe_id
    hydraulic_map: dict[str, dict] = {}
    for suspect in hydraulic_suspects:
        pid = suspect["pipe_id"]
        hydraulic_map[pid] = suspect

    # Index acoustic events by pipe_segment
    acoustic_map: dict[str, list[AcousticEvent]] = {}
    for evt in acoustic_events:
        seg = evt.pipe_segment
        if seg not in acoustic_map:
            acoustic_map[seg] = []
        acoustic_map[seg].append(evt)

    # Collect all unique pipe IDs from both sources
    all_pipe_ids: set[str] = set(hydraulic_map.keys()) | set(acoustic_map.keys())

    results: list[dict] = []
    for pid in sorted(all_pipe_ids):
        evidence: list[str] = []

        # Hydraulic confidence
        p_h = 0.0
        if pid in hydraulic_map:
            p_h = hydraulic_map[pid].get("confidence", 0.0)
            evidence.append("hydraulic_anomaly")

        # Acoustic confidence — derived from max amplitude among events
        # Sigmoid mapping: p_a = amplitude / (amplitude + 60)  (60 dB reference)
        p_a = 0.0
        if pid in acoustic_map:
            max_amp = max(evt.amplitude_db for evt in acoustic_map[pid])
            p_a = max_amp / (max_amp + 60.0) if (max_amp + 60.0) > 0 else 0.0
            evidence.append("acoustic_signature")

        # Bayesian-style combination: combined = 1 - (1 - p_h) * (1 - p_a)
        combined = 1.0 - (1.0 - p_h) * (1.0 - p_a)

        results.append({
            "pipe_id": pid,
            "combined_confidence": round(combined, 6),
            "evidence": evidence,
        })

    # Sort by combined confidence descending
    results.sort(key=lambda r: r["combined_confidence"], reverse=True)

    return results
