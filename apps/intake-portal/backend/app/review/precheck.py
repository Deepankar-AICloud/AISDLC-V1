"""Approval pre-check: show "Approve" only when GitHub would accept and count it.

Advisory only. The approval itself is still sent with the user's own token and
GitHub's answer is final. When GitHub rejects, its message is shown verbatim and
the portal never retries with another identity.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from ..github import codeowners
from ..github.clients import ServiceGitHubClient
from ..github.http import GitHubError

WRITE_LEVELS = {"write", "maintain", "admin"}
STAGE_BRANCH = re.compile(r"^sdlc/issue-(\d+)/([a-z_-]+)$")


@dataclass
class Check:
    rule: str
    ok: bool | None  # None = could not determine / warning only
    detail: str


@dataclass
class Precheck:
    can_approve: bool
    checks: list[Check] = field(default_factory=list)
    head_sha: str = ""
    stage: str = ""

    @property
    def reasons(self) -> list[str]:
        return [c.detail for c in self.checks if c.ok is False]

    def to_dict(self) -> dict[str, Any]:
        return {
            "can_approve": self.can_approve,
            "head_sha": self.head_sha,
            "stage": self.stage,
            "checks": [asdict(c) for c in self.checks],
            "reasons": self.reasons,
        }


def stage_of(pr: dict[str, Any]) -> tuple[int | None, str]:
    m = STAGE_BRANCH.match(pr.get("head", {}).get("ref", ""))
    return (int(m.group(1)), m.group(2)) if m else (None, "")


def _owner_matches(svc: ServiceGitHubClient, owner: str, login: str) -> bool:
    if not owner.startswith("@"):
        return False  # email owners cannot be resolved to a login safely
    name = owner[1:]
    if "/" in name:
        org, slug = name.split("/", 1)
        return svc.team_member(org, slug, login)
    return name.lower() == login.lower()


def approval_precheck(
    svc: ServiceGitHubClient,
    *,
    pr: dict[str, Any],
    files: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
    login: str,
    issue_number: int,
    base_branch: str,
    codeowners_policy: str = "strict",
    separation_of_duties: bool = False,
    sod_stages: list[str] | None = None,
    requester_login: str | None = None,
) -> Precheck:
    checks: list[Check] = []
    head_sha = pr.get("head", {}).get("sha", "")
    pr_issue, stage = stage_of(pr)

    open_ = pr.get("state") == "open" and not pr.get("merged") and not pr.get("draft")
    checks.append(
        Check(
            "pr_open",
            open_,
            "The pull request is open."
            if open_
            else "The pull request is closed, merged or a draft, so it cannot be approved.",
        )
    )
    linked = pr_issue == issue_number
    checks.append(
        Check(
            "sdlc_stage_pr",
            linked,
            f"This is the {stage.upper()} stage PR for issue #{issue_number}."
            if linked
            else "This PR is not an AISDLC stage PR for this request.",
        )
    )

    perm = svc.collaborator_permission(login)
    has_write = perm in WRITE_LEVELS
    checks.append(
        Check(
            "write_access",
            has_write,
            f"You have '{perm}' access."
            if has_write
            else f"Your GitHub account '{login}' has '{perm}' access; write access is needed for an approval to count.",
        )
    )

    author = pr.get("user", {}).get("login", "")
    not_author = author.lower() != login.lower()
    checks.append(
        Check(
            "not_author",
            not_author,
            f"The PR was opened by {author}."
            if not_author
            else "You opened this pull request; GitHub does not let authors approve their own PR.",
        )
    )

    # CODEOWNERS (from the base branch, as GitHub does)
    text = next((t for loc in codeowners.LOCATIONS if (t := svc.get_file(loc, base_branch)) is not None), None)
    errors = svc.codeowners_errors()
    if text is None:
        checks.append(
            Check(
                "codeowner",
                False if codeowners_policy == "strict" else None,
                "The repository has no CODEOWNERS file, so code-owner approval cannot be verified.",
            )
        )
    else:
        rules = codeowners.parse(text)
        owned: list[str] = []
        unowned: list[str] = []
        for f in files:
            owners = codeowners.owners_for(rules, f["filename"])
            if owners and any(_owner_matches(svc, o, login) for o in owners):
                owned.append(f["filename"])
            else:
                unowned.append(f["filename"])
        ok_owner = bool(owned)
        detail = (
            f"You are a code owner for {len(owned)} of {len(files)} changed file(s)."
            if ok_owner
            else "You are not a code owner for any changed file in this PR."
        )
        if ok_owner and unowned:
            detail += " Other code owners must approve: " + ", ".join(unowned[:5]) + ("…" if len(unowned) > 5 else "")
        if errors:
            detail += f" GitHub reports {len(errors)} CODEOWNERS error(s) (for example unknown owners)."
        checks.append(Check("codeowner", ok_owner if ok_owner or codeowners_policy == "strict" else None, detail))

    # Branch protection / rulesets
    try:
        protection = svc.branch_protection(base_branch)
        rules_list = svc.branch_rules(base_branch)
    except GitHubError as exc:
        checks.append(
            Check(
                "branch_protection",
                None,
                f"Branch protection could not be read ({exc.status}); GitHub will enforce it.",
            )
        )
    else:
        if protection is None and not rules_list:
            checks.append(
                Check(
                    "branch_protection",
                    None,
                    f"'{base_branch}' has no branch protection. GitHub will not require this approval, "
                    "but approving still merges the PR and starts the next AISDLC stage.",
                )
            )
        else:
            reviews_cfg = (protection or {}).get("required_pull_request_reviews") or {}
            last_push = bool(reviews_cfg.get("require_last_push_approval"))
            detail = "Branch protection requires reviews"
            if reviews_cfg.get("require_code_owner_reviews"):
                detail += " from code owners"
            if last_push:
                detail += "; the most recent pusher cannot approve"
            checks.append(Check("branch_protection", True, detail + "."))

    if separation_of_duties and stage in (sod_stages or []) and requester_login:
        sod_ok = requester_login.lower() != login.lower()
        checks.append(
            Check(
                "separation_of_duties",
                sod_ok,
                "Separation of duties: you are not the requester."
                if sod_ok
                else f"Separation of duties: the requester cannot approve the "
                f"{stage.upper()} for their own requirement.",
            )
        )

    mine = [
        r
        for r in reviews
        if r.get("user", {}).get("login", "").lower() == login.lower()
        and r.get("state") == "APPROVED"
        and r.get("commit_id") == head_sha
    ]
    checks.append(
        Check(
            "not_already_approved",
            not mine,
            "You have not approved this version yet." if not mine else "You already approved this version of the PR.",
        )
    )

    can = all(c.ok is not False for c in checks)
    return Precheck(can_approve=can, checks=checks, head_sha=head_sha, stage=stage)
