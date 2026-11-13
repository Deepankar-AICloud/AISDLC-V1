"""Completeness hints that mirror the AISDLC readiness gate (`config/readiness.yml`, BRD stage).

A hint only: missing items never block submission; AISDLC asks for them.
"""

from __future__ import annotations

from typing import Any

MANDATORY: dict[str, tuple[str, list[str]]] = {
    "business_problem": (
        "Business problem",
        ["problem", "pain", "need", "request", "require", "cannot", "unable", "lack", "want", "missing"],
    ),
    "business_objective": (
        "Objective",
        [
            "objective",
            "goal",
            "outcome",
            "so that",
            "enable",
            "provide",
            "allow",
            "improve",
            "reduce",
            "access",
            "support",
            "automate",
        ],
    ),
    "stakeholders": (
        "Stakeholders",
        [
            "employee",
            "manager",
            "user",
            "stakeholder",
            "customer",
            "admin",
            "reviewer",
            "role",
            "team",
            "security",
            "auditor",
        ],
    ),
}
OPTIONAL: dict[str, tuple[str, list[str]]] = {
    "scope": ("Scope", ["scope", "include", "exclude", "out of scope"]),
    "constraints": (
        "Constraints",
        ["constraint", "limitation", "must not", "compliance", "gdpr", "regulation", "policy"],
    ),
}
FIELD_FOR = {
    "business_problem": "business_problem",
    "business_objective": "objective",
    "stakeholders": "stakeholders",
    "scope": "scope",
    "constraints": "constraints",
}
GUIDANCE = {
    "business_problem": "What is not working today, and for whom?",
    "business_objective": "What outcome should the change achieve? How will you know it worked?",
    "stakeholders": "Who is affected or needs to approve (roles or teams)?",
    "scope": "What is included, and what is explicitly out of scope?",
    "constraints": "Deadlines, compliance, policy, technology or budget limits.",
}


def completeness(fields: dict[str, str], all_text: str) -> dict[str, Any]:
    text = all_text.lower()
    items: list[dict[str, Any]] = []
    for group, mandatory in ((MANDATORY, True), (OPTIONAL, False)):
        for key, (label, kws) in group.items():
            filled = bool(fields.get(FIELD_FOR[key], "").strip())
            detected = filled or any(k in text for k in kws)
            items.append(
                {
                    "key": key,
                    "label": label,
                    "mandatory": mandatory,
                    "field_filled": filled,
                    "detected": detected,
                    "guidance": GUIDANCE[key],
                }
            )
    missing = [i["label"] for i in items if i["mandatory"] and not i["detected"]]
    return {
        "items": items,
        "missing_mandatory": missing,
        "hint": (
            "Looks complete for the readiness check."
            if not missing
            else f"AISDLC will probably ask about: {', '.join(missing)}. You can still submit."
        ),
        "min_chars_ok": len(all_text.strip()) >= 25,
    }
