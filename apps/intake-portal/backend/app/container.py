"""Wires settings, database, GitHub clients and helpers. One instance per app."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import httpx
import yaml

from .config import Settings
from .db import Database
from .github.app_auth import GitHubOAuth, InstallationTokenProvider
from .github.clients import ServiceGitHubClient
from .github.fake import FakeGitHub
from .github.http import GitHubError, GitHubHTTP
from .security import RateLimiter, TokenCipher

log = logging.getLogger(__name__)


class Container:
    def __init__(self, settings: Settings, fake: FakeGitHub | None = None) -> None:
        self.settings = settings
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.db = Database(settings.database_url)
        self.db.create_all()
        self.rate = RateLimiter()
        self.cipher = TokenCipher.from_setting(
            settings.token_encryption_key.get_secret_value(),
            settings.data_dir / "dev-token.key" if settings.app_env != "production" else None,
        )
        transport: httpx.BaseTransport | None = None
        self.fake: FakeGitHub | None = None
        if settings.github_mode == "fake":
            self.fake = fake or FakeGitHub()
            transport = self.fake.transport()
            owner, repo = self.fake.owner, self.fake.repo
        else:
            owner, repo = settings.repo_owner, settings.repo_name
        self.owner, self.repo = owner, repo
        self.http = GitHubHTTP(settings.github_api_url, transport=transport, max_retries=settings.github_max_retries)
        self.web_http = GitHubHTTP(settings.github_web_url, transport=transport, max_retries=1)
        if self.fake is not None:
            fake_ref = self.fake

            def token_provider() -> str:
                return fake_ref.installation_token

            self.token_provider = token_provider
            authorize_base = settings.public_base_url.rstrip("/") + "/dev/fake-github"
        else:
            self.token_provider = InstallationTokenProvider(
                self.http,
                app_id=settings.github_app_id,
                private_key=settings.app_private_key(),
                owner=owner,
                repo=repo,
                installation_id=settings.github_app_installation_id,
            )
            authorize_base = settings.github_web_url
        self.service = ServiceGitHubClient(self.http, self.token_provider, owner, repo)
        self.oauth = GitHubOAuth(
            self.web_http,
            authorize_base,
            settings.github_app_client_id or "fake-client-id",
            settings.github_app_client_secret.get_secret_value() or "fake-secret",
            settings.public_base_url.rstrip("/") + "/auth/github/callback",
        )
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_lock = threading.Lock()

    @property
    def repository(self) -> str:
        return f"{self.owner}/{self.repo}"

    def cached(self, key: str, ttl: float, fn: Any) -> Any:
        with self._cache_lock:
            hit = self._cache.get(key)
            if hit and time.monotonic() - hit[0] < ttl:
                return hit[1]
        value = fn()
        with self._cache_lock:
            self._cache[key] = (time.monotonic(), value)
        return value

    def repo_info(self) -> dict[str, Any]:
        def load() -> dict[str, Any]:
            try:
                r = self.service.get_repo()
                return {
                    "full_name": r.get("full_name", self.repository),
                    "private": bool(r.get("private")),
                    "url": r.get("html_url", ""),
                }
            except GitHubError as exc:
                log.warning("repo info unavailable", extra={"fields": {"status": exc.status}})
                return {"full_name": self.repository, "private": None, "url": ""}

        return self.cached("repo", 600, load)

    def allowed_models(self) -> list[str]:
        def load() -> list[str]:
            text = self.service.get_file("config/models.yml", self.settings.github_base_branch)
            models: set[str] = set()
            if text:
                try:
                    cfg = yaml.safe_load(text) or {}
                    for tier in (cfg.get("tiers") or {}).values():
                        for k in ("preferred", "fallback"):
                            if isinstance(tier.get(k), dict) and tier[k].get("model"):
                                models.add(str(tier[k]["model"]))
                except yaml.YAMLError:
                    log.warning("config/models.yml could not be parsed")
            return sorted(models) or ["gpt-5", "gpt-5-mini", "claude-sonnet-5"]

        try:
            return self.cached("models", 600, load)
        except GitHubError:
            return []
