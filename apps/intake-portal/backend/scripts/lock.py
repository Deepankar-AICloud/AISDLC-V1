"""Regenerate requirements.lock / requirements-dev.lock (universal, pinned, sha256 hashes only).

Usage: python scripts/lock.py   (needs `uv`; honours UV_INDEX_URL for private mirrors)
Some mirrors return md5 hashes, which pip rejects with --require-hashes; they are removed here.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ["uv", "pip", "compile", "pyproject.toml", "--universal", "--python-version", "3.12", "-q", "--no-header"]


def strip_md5(path: Path) -> None:
    blocks: list[list[str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith((" ", "#")):
            blocks.append([line])
        elif blocks and line.strip():
            blocks[-1].append(line)
    out: list[str] = []
    for b in blocks:
        head = b[0].rstrip(" \\").rstrip()
        hashes = [ln.strip().rstrip(" \\").strip() for ln in b[1:] if ln.strip().startswith("--hash=sha256:")]
        comments = [ln for ln in b[1:] if ln.strip().startswith("#")]
        if not hashes:
            sys.exit(f"no sha256 hash for {head}")
        lines = [head + " \\"] + [f"    {h} \\" for h in hashes]
        lines[-1] = lines[-1].rstrip(" \\")
        out += lines + comments
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> None:
    subprocess.run([*BASE, "--extra", "postgres", "--generate-hashes", "-o", "requirements.lock"], cwd=ROOT, check=True)
    strip_md5(ROOT / "requirements.lock")
    subprocess.run([*BASE, "--extra", "dev", "-o", "requirements-dev.lock"], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
