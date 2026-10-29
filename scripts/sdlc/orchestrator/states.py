"""Explicit workflow states and legal transitions for the Agentic SDLC."""
from __future__ import annotations

from enum import Enum


class State(str, Enum):
    REQUIREMENT_RECEIVED = "REQUIREMENT_RECEIVED"

    BRD_GENERATION = "BRD_GENERATION"
    BRD_QC = "BRD_QC"
    BRD_HUMAN_REVIEW = "BRD_HUMAN_REVIEW"
    BRD_APPROVED = "BRD_APPROVED"

    PRD_GENERATION = "PRD_GENERATION"
    PRD_QC = "PRD_QC"
    PRD_HUMAN_REVIEW = "PRD_HUMAN_REVIEW"
    PRD_APPROVED = "PRD_APPROVED"

    EPIC_GENERATION = "EPIC_GENERATION"
    EPIC_QC = "EPIC_QC"
    EPIC_HUMAN_REVIEW = "EPIC_HUMAN_REVIEW"
    EPIC_APPROVED = "EPIC_APPROVED"

    ARCHITECTURE_GENERATION = "ARCHITECTURE_GENERATION"
    ARCHITECTURE_QC = "ARCHITECTURE_QC"
    ARCHITECTURE_HUMAN_REVIEW = "ARCHITECTURE_HUMAN_REVIEW"
    ARCHITECTURE_APPROVED = "ARCHITECTURE_APPROVED"

    NFR_GENERATION = "NFR_GENERATION"
    NFR_QC = "NFR_QC"
    NFR_HUMAN_REVIEW = "NFR_HUMAN_REVIEW"
    NFR_APPROVED = "NFR_APPROVED"

    TASK_GENERATION = "TASK_GENERATION"
    TASK_QC = "TASK_QC"
    TASK_APPROVED = "TASK_APPROVED"

    CODE_GENERATION = "CODE_GENERATION"
    CODE_QC = "CODE_QC"
    CODE_HUMAN_REVIEW = "CODE_HUMAN_REVIEW"
    CODE_APPROVED = "CODE_APPROVED"

    DEV_DEPLOYMENT = "DEV_DEPLOYMENT"
    FUNCTIONAL_TESTING = "FUNCTIONAL_TESTING"
    PERFORMANCE_TESTING = "PERFORMANCE_TESTING"
    STAGING_DEPLOYMENT = "STAGING_DEPLOYMENT"
    SECURITY_TESTING = "SECURITY_TESTING"

    RELEASE_READY = "RELEASE_READY"
    RELEASE_APPROVAL = "RELEASE_APPROVAL"
    PRODUCTION_DEPLOYMENT = "PRODUCTION_DEPLOYMENT"
    # Production is only "done" after verification (not merely a successful deploy).
    DEPLOYED_AND_VERIFIED = "DEPLOYED_AND_VERIFIED"
    DEPLOYMENT_FAILED = "DEPLOYMENT_FAILED"

    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NEEDS_HUMAN_INTERVENTION = "NEEDS_HUMAN_INTERVENTION"
    # Generic sub-state: a stage is paused awaiting human model confirmation
    # (separate from artifact approval). Applies to any generation stage.
    AWAITING_MODEL_CONFIRMATION = "AWAITING_MODEL_CONFIRMATION"
    # Generic sub-state: a stage is paused awaiting required information
    # (readiness gate BLOCKED). Resolved when the human supplies the info.
    AWAITING_REQUIRED_INFORMATION = "AWAITING_REQUIRED_INFORMATION"


# Linear happy-path flow for the generation stages (orchestrator computes the
# next state; failures route to FAILED / NEEDS_HUMAN_INTERVENTION).
STAGE_FLOW: dict[str, str] = {
    State.REQUIREMENT_RECEIVED: State.BRD_GENERATION,
    State.BRD_APPROVED: State.PRD_GENERATION,
    State.PRD_APPROVED: State.EPIC_GENERATION,
    State.EPIC_APPROVED: State.ARCHITECTURE_GENERATION,
    State.ARCHITECTURE_APPROVED: State.NFR_GENERATION,
    State.NFR_APPROVED: State.TASK_GENERATION,
    State.TASK_APPROVED: State.CODE_GENERATION,
    State.CODE_APPROVED: State.DEV_DEPLOYMENT,
    State.DEV_DEPLOYMENT: State.FUNCTIONAL_TESTING,
    State.FUNCTIONAL_TESTING: State.PERFORMANCE_TESTING,
    State.PERFORMANCE_TESTING: State.STAGING_DEPLOYMENT,
    State.STAGING_DEPLOYMENT: State.SECURITY_TESTING,
    State.SECURITY_TESTING: State.RELEASE_READY,
    State.RELEASE_READY: State.RELEASE_APPROVAL,
    State.RELEASE_APPROVAL: State.PRODUCTION_DEPLOYMENT,
    State.PRODUCTION_DEPLOYMENT: State.COMPLETED,
}

# Maps a generation state to the agent key in config/agents.yml.
STATE_TO_AGENT: dict[str, str] = {
    State.BRD_GENERATION: "brd",
    State.PRD_GENERATION: "prd",
    State.EPIC_GENERATION: "epic",
    State.ARCHITECTURE_GENERATION: "architecture",
    State.NFR_GENERATION: "nfr",
    State.TASK_GENERATION: "task",
    State.CODE_GENERATION: "code",
}

# Inverse: agent key -> its generation state (used to resume a stage that was
# paused awaiting human model confirmation).
AGENT_TO_STATE: dict[str, str] = {agent: state for state, agent in STATE_TO_AGENT.items()}
