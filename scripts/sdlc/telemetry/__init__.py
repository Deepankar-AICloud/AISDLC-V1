"""Token & cost telemetry.

Captures one record per LLM invocation and computes ESTIMATED cost from the
versioned pricing table. Values that cannot be obtained are recorded as
``null`` with ``usage_source=unavailable`` — never fabricated (prompt rules
27-28). Emits usage.json / usage.csv for a run.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..common.config import pricing_config, run_reports_dir
from ..common.llm import LLMUsage
from ..common.logging_util import now_iso


@dataclass
class TelemetryRecord:
    timestamp: str
    run_id: str
    agent: str
    artifact: str
    stage: str
    provider: str
    requested_model: str
    actual_model: str
    model_version: Optional[str]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    cached_input_tokens: Optional[int]
    cache_write_tokens: Optional[int]
    total_tokens: Optional[int]
    latency_ms: Optional[int]
    retry_count: int
    qc_score: Optional[float]
    status: str
    usage_source: str
    input_cost: Optional[float] = None
    output_cost: Optional[float] = None
    cache_cost: Optional[float] = None
    total_cost: Optional[float] = None
    cost_basis: str = "estimated"  # actual | estimated | unavailable
    recommended_model: Optional[str] = None
    selected_model: Optional[str] = None
    selection_source: Optional[str] = None  # router_recommendation | human_override | automatic | manual_selection
    override_reason: Optional[str] = None


def _price(model: str) -> dict[str, Any] | None:
    return pricing_config().get("models", {}).get(model)


def _cost(tokens: Optional[int], rate_per_million: Optional[float]) -> Optional[float]:
    if tokens is None or rate_per_million is None:
        return None
    return round(tokens / 1_000_000 * rate_per_million, 6)


class Telemetry:
    """Accumulates telemetry records for a single run."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.records: list[TelemetryRecord] = []

    def record(
        self,
        *,
        agent: str,
        artifact: str,
        stage: str,
        usage: LLMUsage,
        retry_count: int = 0,
        qc_score: Optional[float] = None,
        status: str = "ok",
        recommended_model: Optional[str] = None,
        selected_model: Optional[str] = None,
        selection_source: Optional[str] = None,
        override_reason: Optional[str] = None,
    ) -> TelemetryRecord:
        rate = _price(usage.actual_model)
        cost_basis = "estimated" if rate else "unavailable"
        in_cost = _cost(usage.input_tokens, rate.get("input")) if rate else None
        out_cost = _cost(usage.output_tokens, rate.get("output")) if rate else None
        cache_cost = _cost(usage.cached_input_tokens, rate.get("cache_read")) if rate else None
        total_cost = None
        parts = [c for c in (in_cost, out_cost, cache_cost) if c is not None]
        if parts:
            total_cost = round(sum(parts), 6)

        rec = TelemetryRecord(
            timestamp=now_iso(),
            run_id=self.run_id,
            agent=agent,
            artifact=artifact,
            stage=stage,
            provider=usage.provider,
            requested_model=usage.requested_model,
            actual_model=usage.actual_model,
            model_version=usage.model_version,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_input_tokens=usage.cached_input_tokens,
            cache_write_tokens=usage.cache_write_tokens,
            total_tokens=usage.total_tokens,
            latency_ms=usage.latency_ms,
            retry_count=retry_count,
            qc_score=qc_score,
            status=status,
            usage_source=usage.usage_source,
            input_cost=in_cost,
            output_cost=out_cost,
            cache_cost=cache_cost,
            total_cost=total_cost,
            cost_basis=cost_basis,
            recommended_model=recommended_model,
            selected_model=selected_model,
            selection_source=selection_source,
            override_reason=override_reason,
        )
        self.records.append(rec)
        return rec

    def flush(self) -> dict[str, Path]:
        out = run_reports_dir(self.run_id)
        rows = [asdict(r) for r in self.records]

        json_path = out / "usage.json"
        json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

        csv_path = out / "usage.csv"
        if rows:
            with csv_path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
        else:
            csv_path.write_text("", encoding="utf-8")

        return {"json": json_path, "csv": csv_path}

    def totals(self) -> dict[str, Any]:
        def _sum(attr: str) -> float:
            return round(sum(getattr(r, attr) or 0 for r in self.records), 6)

        any_unavailable = any(r.cost_basis != "estimated" for r in self.records)
        return {
            "total_input_tokens": _sum("input_tokens"),
            "total_output_tokens": _sum("output_tokens"),
            "total_cached_tokens": _sum("cached_input_tokens"),
            "total_tokens": _sum("total_tokens"),
            "total_estimated_cost": _sum("total_cost"),
            "cost_basis": "partial" if any_unavailable else "estimated",
            "invocations": len(self.records),
        }
