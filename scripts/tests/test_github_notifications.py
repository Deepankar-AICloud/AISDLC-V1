"""Verify GitHub issue comments notify users at SDLC pipeline milestones."""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def workflow(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def step_index(steps: list[dict], name: str) -> int:
    return next(i for i, step in enumerate(steps) if step.get("name") == name)


class GitHubNotificationWorkflowTests(unittest.TestCase):
    def test_model_confirmation_and_decision_are_issue_comments(self) -> None:
        orchestrator = workflow("agentic-sdlc.yml")["jobs"]["orchestrate"]["steps"]
        model_gate = next(
            step for step in orchestrator if step.get("name") == "Model recommendation gate (await human confirmation)"
        )
        self.assertEqual(model_gate["if"], "steps.outcome.outputs.status == 'AWAITING_MODEL_CONFIRMATION'")
        self.assertIn('gh issue comment "$ISSUE"', model_gate["run"])
        self.assertIn("/model approve", model_gate["run"])
        self.assertIn("github.repository_owner", model_gate["env"]["NOTIFY_USERS"])
        self.assertIn("${NOTIFY_USERS}", model_gate["run"])

        feedback = workflow("feedback-handler.yml")["jobs"]["model"]["steps"]
        decision = next(step for step in feedback if step.get("id") == "decision")
        self.assertIn("Model decision recorded", decision["run"])
        self.assertIn("Resuming the stage", decision["run"])
        self.assertNotIn("MODEL_EMAIL_", str(orchestrator))

    def test_artifact_pr_posts_issue_comment_after_pr_is_available(self) -> None:
        steps = workflow("agentic-sdlc.yml")["jobs"]["orchestrate"]["steps"]
        pr_step = next(step for step in steps if step.get("name") == "Open or update artifact PR (human gate)")
        run = pr_step["run"]
        self.assertLess(run.index("gh pr create"), run.index('gh pr view "$BRANCH" --json url'))
        self.assertLess(run.index('gh pr view "$BRANCH" --json url'), run.rindex('gh issue comment "$ISSUE"'))
        self.assertIn("[Review the pull request](${PR_URL})", run)

    def test_approval_notifies_issue_after_queuing_next_configured_stage(self) -> None:
        steps = workflow("artifact-review.yml")["jobs"]["resume"]["steps"]
        approve = step_index(steps, "Mark stage approved & advance state")
        trigger = step_index(steps, "Trigger next stage")
        notify = step_index(steps, "Notify issue participants that the stage advanced")
        self.assertLess(approve, trigger)
        self.assertLess(trigger, notify)
        self.assertIn("next_stage=$NEXT_STAGE", steps[approve]["run"])
        self.assertIn("The next pipeline stage is **${NEXT_STAGE}**", steps[notify]["run"])
        self.assertIn('gh issue comment "$ISSUE_NUMBER"', steps[notify]["run"])

    def test_brd_approval_is_the_gate_to_prd(self) -> None:
        agents = yaml.safe_load((ROOT / "config" / "agents.yml").read_text(encoding="utf-8"))["agents"]
        self.assertEqual(agents["brd"]["human_review"], "required")
        self.assertEqual(agents["brd"]["next"], "prd")
        self.assertEqual(agents["prd"]["next"], "epic")

    def test_merging_unapproved_sdlc_pr_advances_once(self) -> None:
        review = workflow("artifact-review.yml")
        triggers = review[True]  # PyYAML parses the "on" key as boolean True.
        self.assertEqual(triggers["pull_request"]["types"], ["closed"])
        gate = review["jobs"]["gate"]
        self.assertIn("github.event.pull_request.merged == true", gate["if"])
        self.assertIn('select(.state == "APPROVED")', gate["steps"][0]["run"])
        self.assertEqual(review["jobs"]["resume"]["needs"], "gate")
        self.assertEqual(review["jobs"]["resume"]["if"], "needs.gate.outputs.proceed == 'true'")
