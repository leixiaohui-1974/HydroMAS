"""Process ontology loader and query service.
工艺本体加载与查询服务。

Loads the process ontology from ``data/process_ontology.json`` and provides
simple lookup utilities for entity information and fault modes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DEFAULT_ONTOLOGY_PATH = Path(__file__).resolve().parent.parent / "data" / "process_ontology.json"

_cached_ontology: dict | None = None


def load_ontology(ontology_file: str | Path | None = None) -> dict:
    """Load the process ontology from a JSON file.

    从 JSON 文件加载工艺本体。

    Parameters
    ----------
    ontology_file : str | Path | None
        Path to the ontology JSON file.  Defaults to ``data/process_ontology.json``.

    Returns
    -------
    dict
        The parsed ontology dictionary containing ``entities`` and ``fault_modes``.
    """
    global _cached_ontology

    path = Path(ontology_file) if ontology_file else _DEFAULT_ONTOLOGY_PATH

    if _cached_ontology is not None and ontology_file is None:
        return _cached_ontology

    with open(path, encoding="utf-8") as f:
        ontology = json.load(f)

    if ontology_file is None:
        _cached_ontology = ontology

    return ontology


def query_ontology(ontology: dict, entity: str) -> dict[str, Any]:
    """Query information about a specific entity in the ontology.

    查询本体中特定实体的信息。

    Searches both ``entities`` and ``fault_modes`` sections.

    Parameters
    ----------
    ontology : dict
        The ontology dictionary (from :func:`load_ontology`).
    entity : str
        The entity key to look up (e.g. ``"dissolution"``, ``"pipe_leak"``).

    Returns
    -------
    dict
        A dictionary with the entity information.  If the entity is found in
        ``entities``, it includes ``type: "process"``.  If found in
        ``fault_modes``, it includes ``type: "fault_mode"``.  If not found,
        returns ``{"type": "unknown", "entity": entity, "message": "..."}``.
    """
    entities = ontology.get("entities", {})
    if entity in entities:
        return {"type": "process", "entity": entity, **entities[entity]}

    fault_modes = ontology.get("fault_modes", {})
    if entity in fault_modes:
        return {"type": "fault_mode", "entity": entity, **fault_modes[entity]}

    return {
        "type": "unknown",
        "entity": entity,
        "message": f"Entity '{entity}' not found in ontology.",
    }
