"""Pluggable malware-scan hook.

Set MALWARE_SCAN_HOOK="package.module:function". The function receives
`(filename: str, data: bytes)` and returns a `ScanVerdict` (or any object with
`clean: bool` and `reason: str`). It runs before extraction; a non-clean verdict
rejects the file. The default is a no-op that marks every file clean, so deploy a
real scanner (Microsoft Defender for Storage, ClamAV, a vendor API) for production.
A hook that raises fails closed: the file is rejected.
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from .types import ExtractionError

log = logging.getLogger(__name__)


@dataclass
class ScanVerdict:
    clean: bool
    reason: str = ""


def noop_scan(filename: str, data: bytes) -> ScanVerdict:
    return ScanVerdict(clean=True, reason="no scanner configured")


@lru_cache
def _load(spec: str) -> Callable[[str, bytes], ScanVerdict]:
    if not spec:
        return noop_scan
    module_name, _, func = spec.partition(":")
    fn = getattr(importlib.import_module(module_name), func)
    return fn


def scan_file(spec: str, filename: str, data: bytes) -> None:
    try:
        verdict = _load(spec)(filename, data)
    except Exception as exc:  # noqa: BLE001 - fail closed
        log.error("malware scan hook failed", extra={"fields": {"error_type": type(exc).__name__}})
        raise ExtractionError("scan_failed", f"{filename}: the malware scan could not run; file rejected.") from exc
    if not verdict.clean:
        raise ExtractionError("scan_rejected", f"{filename}: rejected by the malware scan ({verdict.reason}).")
