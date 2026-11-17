export type Me = {
  user: { name: string; email: string; roles: string[]; sign_in: "microsoft" | "github" | "dev" | "password" };
  csrf_token: string;
  github: { connected: boolean; login: string | null; needs_reconnect: boolean };
  config: {
    repository: { full_name: string; private: boolean | null; url: string };
    allowed_extensions: string[];
    feature_ocr: boolean;
    max_files: number;
    max_file_mb: number;
    max_total_mb: number;
    max_pasted_chars: number;
    notice: string;
    auth_mode: "entra" | "dev" | "password";
    github_mode: "app" | "fake";
    reviewer_role: string;
    requester_role: string;
    separation_of_duties: boolean;
  };
};

export type InjectionFlag = { line: number; phrase: string; snippet: string };

export type PreviewFile = {
  id: string;
  filename: string;
  size: number;
  kind: string;
  text: string;
  pages: number | null;
  slides: number | null;
  sheets: number | null;
  chars: number;
  warnings: string[];
  injection_flags: InjectionFlag[];
  error: { code: string; message: string } | null;
};

export type Completeness = {
  items: {
    key: string;
    label: string;
    mandatory: boolean;
    detected: boolean;
    field_filled: boolean;
    guidance: string;
  }[];
  missing_mandatory: string[];
  hint: string;
  min_chars_ok: boolean;
};

export type Preview = {
  draft_id: string;
  files: PreviewFile[];
  issue: {
    title?: string;
    body?: string;
    overflow_comments?: number;
    overflow_preview?: string[];
    visible_chars?: number;
    uses_branch?: boolean;
  };
  plan_error: string | null;
  completeness: Completeness;
  repository: { full_name: string; private: boolean | null };
};

export type StageSummary = {
  run_id: string;
  readiness: string;
  assumptions: string;
  recommended_model: string;
  selected_model: string;
  qc_status: string;
  qc_score: number | null;
  retries: string;
  diagnosis: string;
};

export type Stage = {
  pr_number: number;
  agent: string;
  state: string;
  url: string;
  title: string;
  head_sha: string;
  summary: StageSummary;
};

export type Snapshot = {
  issue?: { number: number; url: string; state: string; title: string };
  labels?: string[];
  status?: string;
  stage?: string;
  questions?: string[];
  questions_url?: string;
  model_pending?: { recommended_model: string; comment_url: string } | null;
  paused_findings?: string[];
  stages?: Stage[];
  open_stage_pr?: number | null;
  latest_run?: { id: number; status: string; conclusion: string | null; url: string } | null;
  sync_error?: string;
};

export type RequestSummary = {
  id: string;
  title: string;
  status: string;
  stage: string;
  issue_number: number | null;
  issue_url: string;
  repository: string;
  created_at: string;
  updated_at: string;
  open_stage_pr: number | null;
};

export type RequestDetail = RequestSummary & {
  snapshot: Snapshot;
  error: string;
  files: {
    filename: string;
    kind: string;
    size: number;
    pages: number | null;
    slides: number | null;
    chars: number;
    warnings: string[];
  }[];
  overflow_branch: string;
  overflow_parts: { total: number; posted: number };
  submit_step: string;
  last_synced_at: string | null;
  is_requester: boolean;
};

export type Check = { rule: string; ok: boolean | null; detail: string };

export type StageView = {
  pr: {
    number: number;
    title: string;
    url: string;
    state: string;
    author: string;
    head_sha: string;
    head_ref: string;
    body: string;
  };
  stage: string;
  summary: StageSummary;
  artifact: { path: string | null; markdown: string | null };
  quality_report: { path: string | null; markdown: string | null };
  files: { filename: string; status: string; additions: number; deletions: number; patch: string }[];
  reviews: { user: string; state: string; submitted_at: string }[];
  precheck: { can_approve: boolean; head_sha: string; checks: Check[]; reasons: string[] } | null;
  github_link: { connected: boolean; login?: string; reason?: string } | null;
  approve_confirmation: string;
};

export type ProductionRun = {
  run_id: number;
  url: string;
  head_sha: string;
  created_at: string;
  can_approve: boolean;
  reason: string;
  evidence: { name: string; status: string; conclusion: string | null; url: string | null; note: string }[];
};

export type ProductionListing = {
  environment: { exists: boolean; reviewers: string[]; problem: string | null };
  runs: ProductionRun[];
  confirmation_word: string;
};

export type AuditRow = {
  ts: string;
  github_login: string;
  identity: string;
  action: string;
  target: string;
  outcome: string;
  github_status: number | null;
};
