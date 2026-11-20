"""Portal settings. Every variable is documented in `.env.example`.

Safety rules enforced at startup (see `Settings.validate_safety`):
- The dev auth bypass and the fake GitHub backend only work when APP_ENV=development.
- Production requires named reviewer sign-in, a real GitHub App, a token encryption key,
  a webhook secret, process-isolated extraction, and secure cookies.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class UnsafeConfigurationError(RuntimeError):
    """Raised when settings would weaken a security control outside development."""


class Settings(BaseSettings):
    # Settings come only from environment variables. No .env file is read: in Azure the deploy workflow
    # copies them from GitHub Secrets into App Service settings; locally, set them in your shell.
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    # --- Runtime --------------------------------------------------------------
    app_env: Literal["development", "test", "production"] = "production"
    bind_host: str = "0.0.0.0"  # noqa: S104 - container default; dev bypass requires loopback
    public_base_url: str = "http://localhost:8000"
    log_level: str = "INFO"
    data_dir: Path = Path("./var")
    database_url: str = "sqlite:///./var/portal.db"
    session_secret: SecretStr = SecretStr("")
    session_max_age_seconds: int = 8 * 3600
    cors_origins: list[str] = Field(default_factory=list)
    serve_frontend_dir: Path | None = None

    # --- Portal sign-in (Entra ID) -------------------------------------------
    auth_mode: Literal["entra", "dev", "password", "open"] = "entra"
    # "password" and "open" sign everyone in as one shared requester ("open" needs no credentials).
    # GitHub reviews and approvals still require a named user.
    # Operator acknowledgement that an upstream IP allow-list (e.g. App Service access restrictions)
    # fronts the portal. Only then may AUTH_MODE=open run outside local development.
    open_mode_network_restricted: bool = False
    portal_admin_password: SecretStr = SecretStr("")
    entra_tenant_id: str = ""
    entra_client_id: str = ""
    entra_client_secret: SecretStr = SecretStr("")
    entra_requester_role: str = "Requester"
    entra_reviewer_role: str = "Reviewer"
    # "Sign in with GitHub" for people without a work account (off by default; Entra is the primary sign-in).
    # Users need at least GITHUB_SIGNIN_MIN_ROLE on the repository; they become Requesters, and Reviewers
    # when they have write access or more.
    github_signin_enabled: bool = False
    github_signin_min_role: Literal["read", "triage", "write", "maintain", "admin"] = "triage"
    # Dev users: "login:Role[,Role]:github_login;..." (development only).
    dev_users: str = (
        "alice:Requester:alice-gh;bob:Reviewer:bob-gh;carol:Requester,Reviewer:carol-gh;"
        "dave:Reviewer:dave-gh;erin:Reviewer:erin-gh"
    )
    # Password for the "admin" dev user (Requester and Reviewer), entered in the username/password form.
    # Never written in code: set DEV_ADMIN_PASSWORD in the environment. Unset means no admin user.
    dev_admin_password: SecretStr = SecretStr("")

    # --- GitHub ---------------------------------------------------------------
    github_mode: Literal["app", "fake"] = "app"
    github_api_url: str = "https://api.github.com"
    github_web_url: str = "https://github.com"
    github_repository: str = ""  # owner/name of the AISDLC repository
    github_base_branch: str = "main"
    github_app_id: str = ""
    github_app_slug: str = ""
    github_app_private_key: SecretStr = SecretStr("")
    github_app_private_key_path: Path | None = None
    github_app_installation_id: str = ""
    github_app_client_id: str = ""
    github_app_client_secret: SecretStr = SecretStr("")
    github_webhook_secret: SecretStr = SecretStr("")
    token_encryption_key: SecretStr = SecretStr("")
    github_max_retries: int = 3

    # --- Intake ---------------------------------------------------------------
    max_files: int = 20
    max_file_bytes: int = 25 * 1024 * 1024
    max_total_bytes: int = 100 * 1024 * 1024
    max_request_bytes: int = 110 * 1024 * 1024
    max_pages: int = 500
    max_slides: int = 500
    max_sheet_cells: int = 200_000
    max_extracted_chars_per_file: int = 2_000_000
    max_pasted_chars: int = 500_000
    extraction_timeout_seconds: int = 60
    extraction_isolation: Literal["process", "inline"] = "process"
    extraction_memory_mb: int = 1024
    zip_max_entries: int = 5000
    zip_max_uncompressed_bytes: int = 300 * 1024 * 1024
    zip_max_ratio: int = 150
    feature_ocr: bool = False
    malware_scan_hook: str = ""  # "module:function"; empty = no-op
    draft_ttl_minutes: int = 120
    issue_body_budget: int = 60_000
    issue_comment_budget: int = 60_000
    max_issue_visible_chars: int = 900_000
    overflow_branch_enabled: bool = True
    upload_originals: bool = True
    allow_public_repo_uploads: bool = False
    retain_extracted_text_days: int = 0
    idempotency_window_minutes: int = 15

    # --- Review policy --------------------------------------------------------
    codeowners_policy: Literal["strict", "advisory"] = "strict"
    separation_of_duties: bool = False
    sod_stages: list[str] = Field(default_factory=lambda: ["brd", "prd"])
    default_reviewers: list[str] = Field(default_factory=list)  # GitHub logins
    block_shell_metacharacters: bool = True
    production_confirmation_word: str = "promote"
    production_workflow_file: str = "deploy-production.yml"
    production_environment: str = "production"
    # Workflow run names shown as release evidence (must match `name:` in the repo's workflows).
    production_evidence_workflows: list[str] = Field(
        default_factory=lambda: [
            "CI — SmartServe Build & Test",
            "CodeQL",
            "Security — Secret Scan",
            "Deploy — DEV",
            "Deploy — STAGING",
        ]
    )

    # --- Status tracking ------------------------------------------------------
    poll_interval_seconds: int = 120
    poller_enabled: bool = True

    # --- Rate limits (per user, per minute) -----------------------------------
    rate_limit_submit_per_min: int = 6
    rate_limit_actions_per_min: int = 30
    rate_limit_reads_per_min: int = 240
    rate_limit_login_per_min: int = Field(default=10, ge=1)

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"

    @property
    def repo_owner(self) -> str:
        return self.github_repository.split("/", 1)[0] if "/" in self.github_repository else ""

    @property
    def repo_name(self) -> str:
        return self.github_repository.split("/", 1)[1] if "/" in self.github_repository else ""

    def app_private_key(self) -> str:
        if self.github_app_private_key.get_secret_value():
            return self.github_app_private_key.get_secret_value().replace("\\n", "\n")
        if self.github_app_private_key_path and self.github_app_private_key_path.exists():
            return self.github_app_private_key_path.read_text(encoding="utf-8")
        return ""

    @property
    def entra_configured(self) -> bool:
        return bool(self.entra_tenant_id and self.entra_client_id and self.entra_client_secret.get_secret_value())

    @model_validator(mode="after")
    def validate_safety(self) -> Settings:
        if self.auth_mode == "password":
            password = self.portal_admin_password.get_secret_value()
            if not password:
                raise UnsafeConfigurationError("AUTH_MODE=password requires PORTAL_ADMIN_PASSWORD.")
            if self.app_env == "production" and len(password) < 12:
                raise UnsafeConfigurationError("PORTAL_ADMIN_PASSWORD must be at least 12 characters in production.")
            if not self.github_signin_enabled and not self.entra_configured:
                raise UnsafeConfigurationError(
                    "Password sign-in requires a named reviewer sign-in: GITHUB_SIGNIN_ENABLED or Entra settings."
                )
        if self.auth_mode in ("password", "open"):
            if self.app_env == "development" and (
                self.bind_host not in ("127.0.0.1", "localhost", "::1")
                or urlsplit(self.public_base_url).hostname not in ("127.0.0.1", "localhost", "::1")
            ):
                raise UnsafeConfigurationError(f"Development AUTH_MODE={self.auth_mode} requires loopback hosting.")
            # Anonymous visitors can create GitHub issues, so open mode binds publicly only behind an IP allow-list.
            if (
                self.auth_mode == "open"
                and not self.open_mode_network_restricted
                and self.bind_host not in ("127.0.0.1", "localhost", "::1")
            ):
                raise UnsafeConfigurationError(
                    "AUTH_MODE=open requires BIND_HOST to be a loopback address "
                    "(or OPEN_MODE_NETWORK_RESTRICTED=true behind an IP allow-list)."
                )
            if self.github_mode == "app":
                missing = [
                    name
                    for name, value in {
                        "GITHUB_REPOSITORY": self.github_repository,
                        "GITHUB_APP_ID": self.github_app_id,
                        "GITHUB_APP_CLIENT_ID": self.github_app_client_id,
                        "GITHUB_APP_CLIENT_SECRET": self.github_app_client_secret.get_secret_value(),
                    }.items()
                    if not value
                ]
                if not self.app_private_key():
                    missing.append("GITHUB_APP_PRIVATE_KEY or GITHUB_APP_PRIVATE_KEY_PATH")
                if missing:
                    raise UnsafeConfigurationError("Missing real GitHub settings: " + ", ".join(missing))
        dev_only: list[str] = []
        if self.auth_mode == "dev":
            dev_only.append("AUTH_MODE=dev")
        if self.auth_mode == "open" and not self.open_mode_network_restricted:
            dev_only.append("AUTH_MODE=open")
        if self.github_mode == "fake":
            dev_only.append("GITHUB_MODE=fake")
        if dev_only and self.app_env not in ("development", "test"):
            raise UnsafeConfigurationError(f"{', '.join(dev_only)} is only allowed when APP_ENV=development or test.")
        if (
            self.auth_mode == "dev"
            and self.app_env == "development"
            and self.bind_host
            not in (
                "127.0.0.1",
                "localhost",
                "::1",
            )
        ):
            raise UnsafeConfigurationError("AUTH_MODE=dev requires BIND_HOST to be a loopback address.")
        if self.app_env == "production":
            missing = [
                name
                for name, value in {
                    "SESSION_SECRET": self.session_secret.get_secret_value(),
                    "GITHUB_REPOSITORY": self.github_repository,
                    "GITHUB_APP_ID": self.github_app_id,
                    "GITHUB_APP_CLIENT_ID": self.github_app_client_id,
                    "GITHUB_APP_CLIENT_SECRET": self.github_app_client_secret.get_secret_value(),
                    "GITHUB_WEBHOOK_SECRET": self.github_webhook_secret.get_secret_value(),
                    "TOKEN_ENCRYPTION_KEY": self.token_encryption_key.get_secret_value(),
                }.items()
                if not value
            ]
            if self.auth_mode == "entra":
                missing += [
                    name
                    for name, value in {
                        "ENTRA_TENANT_ID": self.entra_tenant_id,
                        "ENTRA_CLIENT_ID": self.entra_client_id,
                        "ENTRA_CLIENT_SECRET": self.entra_client_secret.get_secret_value(),
                    }.items()
                    if not value
                ]
            if not self.app_private_key():
                missing.append("GITHUB_APP_PRIVATE_KEY or GITHUB_APP_PRIVATE_KEY_PATH")
            if missing:
                raise UnsafeConfigurationError("Missing required production settings: " + ", ".join(missing))
            if self.extraction_isolation != "process":
                raise UnsafeConfigurationError("EXTRACTION_ISOLATION must be 'process' in production.")
            if not self.public_base_url.startswith("https://"):
                raise UnsafeConfigurationError("PUBLIC_BASE_URL must use https in production.")
            if len(self.session_secret.get_secret_value()) < 32:
                raise UnsafeConfigurationError("SESSION_SECRET must be at least 32 characters.")
        return self

    @property
    def secure_cookies(self) -> bool:
        return self.public_base_url.startswith("https://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
