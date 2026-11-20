from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.intake_routes import request_dict
from app.config import Settings
from app.db import IntakeRequest
from app.github.fake import FakeGitHub
from app.main import create_app

CLEAR_REQUIREMENT = (
    "Business problem: managers cannot see the status of access requests. "
    "Objective: reduce turnaround and improve visibility. Stakeholders: employees, managers and the security team."
)


class Portal:
    """One app + fake GitHub, with a TestClient (cookie jar) per signed-in user."""

    def __init__(self, tmp_path, **overrides: Any) -> None:
        params: dict[str, Any] = dict(
            app_env="test",
            auth_mode="dev",
            github_mode="fake",
            bind_host="127.0.0.1",
            database_url=f"sqlite:///{tmp_path / 'portal.db'}",
            data_dir=tmp_path / "var",
            poller_enabled=False,
            extraction_isolation="inline",
            public_base_url="http://testserver",
            rate_limit_submit_per_min=1000,
            rate_limit_actions_per_min=1000,
            rate_limit_reads_per_min=1000,
        )
        params.update(overrides)
        self.fake: FakeGitHub = params.pop("fake", None) or FakeGitHub()
        self.settings = Settings(**params)
        self.app = create_app(self.settings, fake=self.fake)
        self.container = self.app.state.container
        self.clients: dict[str, TestClient] = {}
        self.responses: list[str] = []

    def client(self, username: str) -> TestClient:
        if username not in self.clients:
            c = TestClient(self.app, follow_redirects=False)
            r = c.post("/auth/dev-login", json={"username": username})
            assert r.status_code == 200, r.text
            c.headers["X-CSRF-Token"] = r.json()["csrf_token"]
            original = c.request

            def recording(method: str, url: str, **kw: Any):  # type: ignore[no-untyped-def]
                resp = original(method, url, **kw)
                self.responses.append(resp.text)
                return resp

            c.request = recording  # type: ignore[method-assign]
            self.clients[username] = c
        return self.clients[username]

    def connect(self, username: str, github_login: str) -> None:
        c = self.client(username)
        r = c.get("/auth/github/connect")
        assert r.status_code == 302
        state = r.headers["location"].split("state=")[1].split("&")[0]
        r = c.post("/dev/fake-github/login/oauth/authorize", data={"login": github_login, "state": state})
        assert r.status_code == 302
        r = c.get(r.headers["location"].replace("http://testserver", ""))
        assert r.status_code == 302 and "github=connected" in r.headers["location"], r.headers.get("location")

    def preview(
        self,
        username: str,
        pasted: str = "",
        files: list[tuple[str, bytes]] | None = None,
        fields: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        import json

        r = self.client(username).post(
            "/api/intake/preview",
            data={"pasted_text": pasted, "fields": json.dumps(fields or {})},
            files=[("files", (n, d, "application/octet-stream")) for n, d in (files or [])],
        )
        assert r.status_code == 200, r.text
        return r.json()

    def submit(self, username: str, draft_id: str, key: str | None = None, **body: Any) -> Any:
        return self.client(username).post(
            "/api/requests", json={"draft_id": draft_id, **body}, headers={"Idempotency-Key": key or uuid.uuid4().hex}
        )

    def request_data(self, request_id: str) -> dict[str, Any]:
        with self.container.db.sessionmaker() as db:
            record = db.get(IntakeRequest, request_id)
            assert record is not None
            return request_dict(record, detail=True)

    def submit_text(self, username: str, text: str, **kw: Any) -> dict[str, Any]:
        d = self.preview(username, pasted=text, **kw)
        r = self.submit(username, d["draft_id"])
        assert r.status_code == 200, r.text
        request = r.json()["request"]
        request.update(self.request_data(request["id"]))
        return request


@pytest.fixture
def portal_factory(tmp_path) -> Callable[..., Portal]:
    made: list[Portal] = []

    def make(**overrides: Any) -> Portal:
        p = Portal(tmp_path / f"p{len(made)}", **overrides)
        made.append(p)
        return p

    return make


@pytest.fixture
def portal(portal_factory) -> Portal:
    return portal_factory()
