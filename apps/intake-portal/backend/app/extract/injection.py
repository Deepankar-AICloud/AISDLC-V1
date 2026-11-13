"""Flag likely prompt-injection phrases for the user. Never alters the text."""

from __future__ import annotations

import re

from .types import InjectionFlag

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "ignore previous instructions",
        re.compile(
            r"\b(ignore|disregard|forget|override)\b[^.\n]{0,40}\b(previous|prior|above|earlier|all|any|system)\b"
            r"[^.\n]{0,20}\b(instructions?|prompts?|rules?|directions?)\b",
            re.I,
        ),
    ),
    ("role reassignment", re.compile(r"\byou are (now|no longer)\b|\bact as (an?|the)\b|\bpretend to be\b", re.I)),
    ("system prompt reference", re.compile(r"\b(system|developer) (prompt|message|mode)\b", re.I)),
    ("new instructions", re.compile(r"\b(new|updated|real) instructions?\b", re.I)),
    (
        "approval manipulation",
        re.compile(r"\b(auto[- ]?approve|approve (this|the) (pr|pull request|stage)|merge without review)\b", re.I),
    ),
    ("pipeline command", re.compile(r"^\s*/(agent|model)\s+\w+", re.I | re.M)),
    (
        "credential request",
        re.compile(
            r"\b(reveal|print|show|send|exfiltrate)\b[^.\n]{0,30}\b(secret|token|password|" r"api key|credentials?)\b",
            re.I,
        ),
    ),
    ("hidden instruction marker", re.compile(r"<\s*(system|instructions?)\s*>|\[\s*(system|inst)\s*\]", re.I)),
]


def scan(text: str, limit: int = 50) -> list[InjectionFlag]:
    flags: list[InjectionFlag] = []
    line_starts = [0] + [i + 1 for i, c in enumerate(text) if c == "\n"]
    import bisect

    for label, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            line = bisect.bisect_right(line_starts, m.start())
            start = max(0, m.start() - 30)
            snippet = text[start : m.end() + 30].replace("\n", " ").strip()
            flags.append(InjectionFlag(line=line, phrase=label, snippet=snippet[:160]))
            if len(flags) >= limit:
                return flags
    flags.sort(key=lambda f: f.line)
    return flags
