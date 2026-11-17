"""Studio settings, read from environment variables only (never from a committed file)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# In a source checkout, apps/intake-portal/backend/app/studio/settings.py sits five levels below the repo root.
_PARENTS = Path(__file__).resolve().parents
_DEFAULT_SOURCE = _PARENTS[5] if len(_PARENTS) > 5 else Path("/opt/aisdlc")

WEAK_PASSWORDS = {"admin", "password", "changeme", "123456", "studio"}


class StudioSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=False)

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    public_base_url: str = "http://localhost:8001"

    # Shared sign-in. The password has no default: set STUDIO_PASSWORD in the environment
    # (Key Vault reference / Kubernetes secret in Azure).
    studio_username: str = "admin"
    studio_password: SecretStr = SecretStr("")
    session_secret: SecretStr = SecretStr("")
    session_max_age_seconds: int = 8 * 3600

    data_dir: Path = Path("var/studio")
    # Git repository that holds scripts/sdlc + config; each job gets its own clone of HEAD.
    aisdlc_source_dir: Path = _DEFAULT_SOURCE
    orchestrator_python: str = Field(default_factory=lambda: sys.executable)
    use_llm: bool = True
    enable_code_stage: bool = True
    max_concurrent_runs: int = 1
    stage_timeout_seconds: int = 3600
    first_job_number: int = 1001

    max_request_bytes: int = 60 * 1024 * 1024
    max_file_bytes: int = 25 * 1024 * 1024
    max_files: int = 10
    max_requirement_chars: int = 200_000
    extraction_isolation: Literal["process", "inline"] = "process"
    extraction_timeout_seconds: int = 60
    malware_scan_hook: str = ""

    rate_limit_login_per_min: int = 10
    rate_limit_create_per_min: int = 5
    rate_limit_actions_per_min: int = 60

    @property
    def is_prod(self) -> bool:
        return self.app_env == "production"

    @property
    def secure_cookies(self) -> bool:
        return self.public_base_url.startswith("https://")

    @property
    def weak_password(self) -> bool:
        pw = self.studio_password.get_secret_value()
        return pw.lower() in WEAK_PASSWORDS or len(pw) < 12

    @model_validator(mode="after")
    def _validate(self) -> StudioSettings:
        problems: list[str] = []
        if not self.studio_password.get_secret_value():
            problems.append("STUDIO_PASSWORD must be set (it has no default).")
        if not self.studio_username.strip():
            problems.append("STUDIO_USERNAME must not be empty.")
        if self.is_prod:
            if len(self.session_secret.get_secret_value()) < 32:
                problems.append("SESSION_SECRET (32+ random characters) is required in production.")
            if not self.secure_cookies:
                problems.append("PUBLIC_BASE_URL must be https:// in production.")
        if not (self.aisdlc_source_dir / "scripts" / "sdlc" / "run.py").is_file():
            problems.append(f"AISDLC_SOURCE_DIR does not contain scripts/sdlc: {self.aisdlc_source_dir}")
        if self.max_concurrent_runs < 1:
            problems.append("MAX_CONCURRENT_RUNS must be at least 1.")
        if problems:
            raise ValueError("Invalid Studio configuration: " + " ".join(problems))
        return self
