"""Starts the portal for end-to-end tests: development mode, fake GitHub, fresh data dir, built frontend.

Never points at a real GitHub repository. Usage: python scripts/e2e_server.py <port> <samples_dir>
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    samples_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / ".e2e-samples"
    from tests.samples import write_samples

    write_samples(samples_dir)
    data = Path(tempfile.mkdtemp(prefix="portal-e2e-"))
    os.environ.update(
        {
            "APP_ENV": "development",
            "AUTH_MODE": "dev",
            "GITHUB_MODE": "fake",
            "GITHUB_SIGNIN_ENABLED": "true",
            "BIND_HOST": "127.0.0.1",
            "PUBLIC_BASE_URL": f"http://127.0.0.1:{port}",
            "DATA_DIR": str(data),
            "DATABASE_URL": f"sqlite:///{data / 'portal.db'}",
            "SERVE_FRONTEND_DIR": str(ROOT.parent / "frontend" / "dist"),
            "EXTRACTION_ISOLATION": "inline",
            "POLLER_ENABLED": "false",
            "LOG_LEVEL": "WARNING",
        }
    )
    import uvicorn

    from app.main import create_app

    try:
        uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")
    finally:
        shutil.rmtree(data, ignore_errors=True)


if __name__ == "__main__":
    main()
