"""Traceability graph (Priority 8).

Builds a directed graph of stable IDs (REQ → BRD-REQ → PRD-FR → EPIC → FEATURE
→ US → ARCH-COMP → TASK → UT/FT → SEC) by linking IDs that co-occur in the same
artifact file along the stage order. Answers coverage questions and writes
reports/<run-id>/traceability-graph.json.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..common.config import DOCS_DIR, REPO_ROOT, run_reports_dir
from . import ID_PATTERNS, STAGE_ORDER, _iter_text_files
import re

# Downstream stage for each stage (for co-occurrence linking).
_NEXT_STAGE = {STAGE_ORDER[i]: STAGE_ORDER[i + 1] for i in range(len(STAGE_ORDER) - 1)}
_TEST_LABELS = {"UT", "FT"}


def _ids_in(text: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {k: [] for k in ID_PATTERNS}
    for label, pattern in ID_PATTERNS.items():
        found[label] = sorted(set(re.findall(pattern, text)))
    return found


def build_graph(run_id: str) -> dict[str, Any]:
    nodes: set[str] = set()
    edges: set[tuple[str, str]] = set()

    for path in _iter_text_files([DOCS_DIR, REPO_ROOT / "src", REPO_ROOT / "tests"]):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        ids = _ids_in(text)
        for lst in ids.values():
            nodes.update(lst)
        # Link every earlier-stage id to every next-stage id present in this file.
        for stage, nxt in _NEXT_STAGE.items():
            for a in ids.get(stage, []):
                for b in ids.get(nxt, []):
                    edges.add((a, b))

    adj: dict[str, set[str]] = defaultdict(set)
    radj: dict[str, set[str]] = defaultdict(set)
    for a, b in edges:
        adj[a].add(b)
        radj[b].add(a)

    def _reaches(start: str, targets_prefixes: set[str]) -> bool:
        seen, stack = set(), [start]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            if any(cur.startswith(p + "-") for p in targets_prefixes) and cur != start:
                return True
            stack.extend(adj.get(cur, ()))
        return False

    reqs = [n for n in nodes if n.startswith("REQ-") or n.startswith("BRD-REQ-")]
    stories = [n for n in nodes if n.startswith("US-")]

    requirements_without_tests = sorted(
        r for r in reqs if not _reaches(r, _TEST_LABELS)
    )
    stories_without_requirements = sorted(
        s for s in stories if not radj.get(s)
    )

    graph = {
        "run_id": run_id,
        "nodes": sorted(nodes),
        "edges": sorted([list(e) for e in edges]),
        "queries": {
            "requirements_without_tests": requirements_without_tests,
            "stories_without_requirements": stories_without_requirements,
            "requirement_count": len(reqs),
            "story_count": len(stories),
        },
    }
    out = run_reports_dir(run_id) / "traceability-graph.json"
    out.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    return graph
