from __future__ import annotations

from fastapi.testclient import TestClient

from app.status.employee import employee_progress, employee_status
from tests.conftest import CLEAR_REQUIREMENT


def test_employee_status_maps_technical_lifecycle_to_plain_language():
    assert employee_status("awaiting_info", {}) == "more_information_required"
    assert employee_status("closed", {"completed": True}) == "completed"
    assert employee_status("closed", {}) == "rejected"
    assert employee_status("needs_attention", {}) == "under_review"
    progress = employee_progress("more_information_required")
    assert [step["state"] for step in progress] == [
        "completed",
        "completed",
        "delayed",
        "pending",
        "pending",
        "pending",
    ]


def test_employee_request_apis_return_owner_scoped_nontechnical_data(portal):
    draft = portal.preview(
        "alice",
        pasted=CLEAR_REQUIREMENT,
        fields={
            "business_problem": "Managers cannot see request status.",
            "objective": "Reduce turnaround and improve visibility.",
        },
    )
    response = portal.submit("alice", draft["draft_id"])
    assert response.status_code == 200, response.text
    receipt = response.json()["request"]
    assert receipt["title"]
    assert not {
        "snapshot",
        "issue_number",
        "issue_url",
        "repository",
        "stage",
        "open_stage_pr",
        "files",
        "error",
    }.intersection(receipt)
    submitted = receipt
    owner = portal.client("alice")

    detail_response = owner.get(f"/api/employee/requests/{submitted['id']}")
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()
    assert detail["id"] == submitted["id"]
    assert detail["status"] == "under_review"
    assert "managers cannot see" in detail["problem"].lower()
    assert "reduce turnaround" in detail["objective"].lower()
    assert not {
        "snapshot",
        "issue_number",
        "issue_url",
        "repository",
        "stage",
        "open_stage_pr",
        "files",
        "error",
    }.intersection(detail)

    assert owner.get("/api/employee/requests").json()["requests"][0]["id"] == submitted["id"]
    other = portal.client("carol")
    assert other.get(f"/api/employee/requests/{submitted['id']}").status_code == 404
    assert all(row["id"] != submitted["id"] for row in other.get("/api/employee/requests").json()["requests"])


def test_requester_cannot_read_technical_request_details(portal):
    submitted = portal.submit_text("alice", CLEAR_REQUIREMENT)
    requester = portal.client("alice")

    response = requester.get(f"/api/requests/{submitted['id']}")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "role_required"
    assert requester.get("/api/requests?scope=mine").status_code == 403
    assert requester.get(f"/api/requests/{submitted['id']}/audit").status_code == 403


def test_employee_can_answer_with_validated_supporting_file(portal):
    submitted = portal.submit_text("alice", "Lorem ipsum dolor sit amet, consectetur adipiscing elit.")
    portal.connect("alice", "alice-gh")

    response = portal.client("alice").post(
        f"/api/employee/requests/{submitted['id']}/information",
        data={"answer": "Here is the missing business context."},
        files=[("files", ("context.txt", b"Objective: complete the access review.", "text/plain"))],
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"submitted": True}

    comment = next(
        c
        for comments in portal.fake.s.comments.values()
        for c in comments
        if c["user"]["login"] == "alice-gh" and "Here is the missing business context." in c["body"]
    )
    assert "Supporting documents:" in comment["body"]
    branch = next(name for name in portal.fake.s.refs if name.startswith(f"intake/{submitted['id']}-response-"))
    assert any(path.endswith("-context.txt") for path in portal.fake.s.files[branch])


def test_open_mode_uses_per_request_tracking_access_without_sign_in(portal_factory):
    p = portal_factory(auth_mode="open", open_mode_network_restricted=True)
    client = TestClient(p.app)
    login = client.post("/auth/open-session")
    assert login.status_code == 200, login.text
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]

    preview = client.post(
        "/api/intake/preview",
        data={"pasted_text": "Lorem ipsum dolor sit amet, consectetur adipiscing elit.", "fields": "{}"},
    )
    assert preview.status_code == 200, preview.text
    response = client.post(
        "/api/requests",
        json={"draft_id": preview.json()["draft_id"]},
        headers={"Idempotency-Key": "open-mode-request"},
    )
    assert response.status_code == 200, response.text
    receipt = response.json()
    request_id = receipt["request"]["id"]
    token = receipt["tracking_token"]
    assert len(token) >= 40
    assert "tracking_token" not in receipt["request"]

    assert client.get(f"/api/employee/requests/{request_id}").status_code == 404
    assert (
        client.get(f"/api/employee/requests/{request_id}", headers={"X-Request-Access": "wrong-token"}).status_code
        == 404
    )
    detail = client.get(f"/api/employee/requests/{request_id}", headers={"X-Request-Access": token})
    assert detail.status_code == 200, detail.text
    assert detail.json()["id"] == request_id

    second_preview = client.post(
        "/api/intake/preview",
        data={"pasted_text": "Lorem ipsum dolor sit amet, consectetur adipiscing elit.", "fields": "{}"},
    )
    second = client.post(
        "/api/requests",
        json={"draft_id": second_preview.json()["draft_id"]},
        headers={"Idempotency-Key": "open-mode-second-request"},
    )
    assert second.status_code == 200, second.text
    assert second.json()["request"]["id"] != request_id
    assert (
        client.get(
            f"/api/employee/requests/{request_id}",
            headers={"X-Request-Access": second.json()["tracking_token"]},
        ).status_code
        == 404
    )

    # The open portal does not expose a shared list of everybody's submissions.
    listing = client.get("/api/employee/requests")
    assert listing.status_code == 503
