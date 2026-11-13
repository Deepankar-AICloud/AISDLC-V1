"""Bounded extraction worker.

`process` isolation (required in production) runs each file in a fresh, spawned
child process with a hard timeout and, on POSIX, an address-space limit. A hung
or exploding parser is killed without affecting the API process. `inline` runs in
process and is only for tests and local development.
"""

from __future__ import annotations

import contextlib
import multiprocessing as mp
import sys
import threading
from dataclasses import asdict
from typing import Any

from .formats import extract_bytes
from .types import ExtractionError, ExtractionResult, Limits

_CONCURRENCY = threading.BoundedSemaphore(2)


def _child(conn: Any, filename: str, data: bytes, limits: dict[str, Any], memory_mb: int) -> None:
    try:
        if sys.platform != "win32":  # address-space cap (POSIX only)
            import resource

            limit = memory_mb * 1024 * 1024
            with contextlib.suppress(ValueError, OSError):
                resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        result = extract_bytes(filename, data, Limits(**limits))
        conn.send(("ok", result.to_dict()))
    except ExtractionError as exc:
        conn.send(("err", exc.code, exc.message))
    except MemoryError:
        conn.send(("err", "too_large", f"{filename}: the file needs too much memory to process."))
    except Exception:  # noqa: BLE001
        conn.send(("err", "corrupt", f"{filename}: the file could not be read; it may be corrupt."))
    finally:
        conn.close()


def run_extraction(
    filename: str,
    data: bytes,
    limits: Limits,
    *,
    isolation: str = "process",
    timeout: float = 60,
    memory_mb: int = 1024,
) -> ExtractionResult:
    with _CONCURRENCY:
        if isolation == "inline":
            return extract_bytes(filename, data, limits)
        ctx = mp.get_context("spawn")
        parent, child = ctx.Pipe(duplex=False)
        proc = ctx.Process(target=_child, args=(child, filename, data, asdict(limits), memory_mb), daemon=True)
        proc.start()
        child.close()
        try:
            if not parent.poll(timeout):
                raise ExtractionError(
                    "timeout", f"{filename}: extraction took longer than {int(timeout)} seconds and was stopped."
                )
            msg = parent.recv()
        except EOFError as exc:
            raise ExtractionError(
                "corrupt", f"{filename}: the extraction worker stopped unexpectedly (file may be malformed)."
            ) from exc
        finally:
            if proc.is_alive():
                proc.kill()
            proc.join(5)
            parent.close()
        if msg[0] == "ok":
            return ExtractionResult.from_dict(msg[1])
        raise ExtractionError(msg[1], msg[2])
