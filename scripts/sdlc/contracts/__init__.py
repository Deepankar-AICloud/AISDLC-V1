"""Artifact Contract validation (Priority 2).

Every major agent has an input and output contract (config/contracts/*.yml).
The orchestrator validates the INPUT contract before generation and the OUTPUT
contract after generation; output violations are folded into QC so a
contract-violating artifact cannot pass. This keeps downstream agents from
guessing the structure of upstream documents.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

import yaml

from ..common.config import CONFIG_DIR

# agent key -> contract file name under config/contracts/
_AGENT_TO_CONTRACT = {
    "brd": "brd",
    "prd": "prd",
    "epic": "epic",
    "architecture": "architecture",
    "nfr": "nfr",
    "task": "task",
    "code": "code",
    "functional_test": "testing",
}


@dataclass
class ContractResult:
    artifact: str
    ok: bool
    missing_inputs: list[str] = field(default_factory=list)
    missing_outputs: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def load_contract(agent_key: str) -> Optional[dict[str, Any]]:
    name = _AGENT_TO_CONTRACT.get(agent_key)
    if not name:
        return None
    path = CONFIG_DIR / "contracts" / f"{name}.yml"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def validate_input(agent_key: str, context: str,
                   artifacts_present: Iterable[str],
                   source_reference: Optional[str] = None) -> ContractResult:
    c = load_contract(agent_key)
    if not c:
        return ContractResult(agent_key, True)
    present = set(artifacts_present)
    missing: list[str] = []
    for inp in c.get("required_inputs", []):
        if inp.startswith("approved_"):
            upstream = inp[len("approved_"):]
            # 'approved_stories' maps to the epic artifact.
            upstream = {"stories": "epic"}.get(upstream, upstream)
            if upstream not in present:
                missing.append(inp)
        elif inp == "source_reference":
            if not source_reference and not re.search(r"#?\d+|ISSUE", context or "", re.IGNORECASE):
                missing.append(inp)
        else:  # customer_requirement and similar textual inputs
            if not (context or "").strip():
                missing.append(inp)
    return ContractResult(c.get("artifact", agent_key), not missing, missing_inputs=missing)


def validate_output(agent_key: str, content: str) -> ContractResult:
    c = load_contract(agent_key)
    if not c:
        return ContractResult(agent_key, True)
    text = content or ""
    low = text.lower()
    violations: list[str] = []
    missing_outputs: list[str] = []

    for section in c.get("required_outputs", []):
        if section.lower() not in low:
            missing_outputs.append(section)
            violations.append(f"Missing required output: '{section}'")

    rules = c.get("validation_rules", {})
    all_ids: list[str] = []
    for prefix in rules.get("id_prefixes", []) or []:
        matches = re.findall(rf"\b{re.escape(prefix)}\d+\b", text)
        if not matches:
            violations.append(f"No IDs with required prefix '{prefix}'")
        all_ids.extend(matches)
    if rules.get("unique_ids_required"):
        dups = {i for i in all_ids if all_ids.count(i) > 1}
        if dups:
            violations.append(f"Duplicate IDs: {', '.join(sorted(dups))}")
    if rules.get("requires_mermaid") and "```mermaid" not in low:
        violations.append("Expected at least one Mermaid diagram")

    trace = c.get("traceability", {})
    if trace.get("required"):
        for ref in trace.get("references", []) or []:
            if ref.lower() not in low:
                violations.append(f"Missing traceability reference to '{ref}'")

    return ContractResult(c.get("artifact", agent_key), not violations,
                          missing_outputs=missing_outputs, violations=violations)
