"""CODEOWNERS parsing and matching (GitHub semantics: the last matching rule wins)."""

from __future__ import annotations

import re
from dataclasses import dataclass

LOCATIONS = [".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"]


@dataclass
class Rule:
    pattern: str
    owners: list[str]
    regex: re.Pattern[str]
    line: int


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    anchored = pattern.startswith("/")
    p = pattern.lstrip("/")
    directory = p.endswith("/")
    p = p.rstrip("/")
    out = ""
    i = 0
    while i < len(p):
        c = p[i]
        if p.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
            continue
        if p.startswith("/**", i) and i + 3 == len(p):
            out += "/.*"
            i += 3
            continue
        if p.startswith("**", i):
            out += ".*"
            i += 2
            continue
        if c == "*":
            out += "[^/]*"
        elif c == "?":
            out += "[^/]"
        else:
            out += re.escape(c)
        i += 1
    if pattern == "*":
        return re.compile(r".*")
    prefix = "^" if anchored or "/" in pattern.strip("/") else r"^(?:.*/)?"
    suffix = "/.*$" if directory else r"(?:/.*)?$"
    return re.compile(prefix + out + suffix)


def parse(text: str) -> list[Rule]:
    rules: list[Rule] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip() if not raw.strip().startswith("\\#") else raw.strip()
        if not line:
            continue
        parts = line.split()
        rules.append(Rule(parts[0], parts[1:], _glob_to_regex(parts[0]), lineno))
    return rules


def owners_for(rules: list[Rule], path: str) -> list[str]:
    owners: list[str] = []
    for rule in rules:
        if rule.regex.match(path):
            owners = rule.owners
    return owners
