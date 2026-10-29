"""Model performance history.

Aggregates per-artifact/per-model outcomes (QC score, retries, tokens, cost)
across runs so the router can use real historical signal — never invented
values. Persisted under ``.sdlc/model-history.json``.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from ..common.config import STATE_DIR

_PATH = STATE_DIR / "model-history.json"


def _load() -> dict[str, Any]:
    if not _PATH.exists():
        return {}
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record(artifact: str, model: str, *, qc_score: Optional[float],
           retries: int, tokens: Optional[int], cost: Optional[float],
           latency_ms: Optional[int] = None, success: Optional[bool] = None) -> None:
    data = _load()
    bucket = data.setdefault(artifact, {}).setdefault(
        model,
        {"runs": 0, "qc_sum": 0.0, "qc_runs": 0, "retry_sum": 0,
         "token_sum": 0, "token_runs": 0, "cost_sum": 0.0, "cost_runs": 0,
         "latency_sum": 0, "latency_runs": 0, "success_sum": 0, "success_runs": 0},
    )
    bucket["runs"] += 1
    bucket["retry_sum"] += int(retries or 0)
    if qc_score is not None:
        bucket["qc_sum"] += float(qc_score)
        bucket["qc_runs"] += 1
    if tokens is not None:
        bucket["token_sum"] += int(tokens)
        bucket["token_runs"] += 1
    if cost is not None:
        bucket["cost_sum"] += float(cost)
        bucket["cost_runs"] += 1
    if latency_ms is not None:
        bucket["latency_sum"] = bucket.get("latency_sum", 0) + int(latency_ms)
        bucket["latency_runs"] = bucket.get("latency_runs", 0) + 1
    if success is not None:
        bucket["success_sum"] = bucket.get("success_sum", 0) + (1 if success else 0)
        bucket["success_runs"] = bucket.get("success_runs", 0) + 1
    _save(data)


def get(artifact: str, model: str) -> Optional[dict[str, Any]]:
    """Return aggregated stats for (artifact, model), or None if no data."""
    bucket = _load().get(artifact, {}).get(model)
    if not bucket or bucket.get("runs", 0) == 0:
        return None
    runs = bucket["runs"]
    lat_runs = bucket.get("latency_runs", 0)
    suc_runs = bucket.get("success_runs", 0)
    return {
        "runs": runs,
        "avg_qc": round(bucket["qc_sum"] / bucket["qc_runs"], 1) if bucket["qc_runs"] else None,
        "retry_rate": round(bucket["retry_sum"] / runs, 2),
        "avg_tokens": round(bucket["token_sum"] / bucket["token_runs"]) if bucket["token_runs"] else None,
        "avg_cost": round(bucket["cost_sum"] / bucket["cost_runs"], 6) if bucket["cost_runs"] else None,
        "avg_latency_ms": round(bucket.get("latency_sum", 0) / lat_runs) if lat_runs else None,
        "success_rate": round(bucket.get("success_sum", 0) / suc_runs, 2) if suc_runs else None,
    }
