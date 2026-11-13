import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError, errorText } from "../api";
import { isReviewer, useMe } from "../App";
import { Diff, Markdown } from "../components/Markdown";
import { Alert, ConfirmDialog, Loading } from "../components/ui";
import type { StageView } from "../types";

type Tab = "artifact" | "diff" | "qc" | "model";
const COMMANDS = [
  { value: "regenerate", label: "Regenerate the artifact" },
  { value: "rerun-qc", label: "Re-run QC" },
  { value: "explain", label: "Explain the artifact" },
  { value: "status", label: "Report status" },
  { value: "impact", label: "Impact analysis" },
];

function CheckList({ view }: { view: StageView }) {
  const pc = view.precheck;
  if (!pc) return null;
  return (
    <ul className="checks" aria-label="Approval checks">
      {pc.checks.map((c) => (
        <li key={c.rule}>
          <span className="icon" aria-hidden="true">
            {c.ok === true ? "✓" : c.ok === false ? "✗" : "!"}
          </span>
          <span>
            <span className="sr-only">{c.ok === true ? "Passed: " : c.ok === false ? "Failed: " : "Note: "}</span>
            {c.detail}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function StageReviewPage() {
  const { id = "", pr = "" } = useParams();
  const { me } = useMe();
  const [view, setView] = useState<StageView | null>(null);
  const [tab, setTab] = useState<Tab>("artifact");
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ kind: "ok" | "error"; text: string; reasons?: string[] } | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [reviewed, setReviewed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notes, setNotes] = useState("");
  const [command, setCommand] = useState("status");

  const load = useCallback(async () => {
    try {
      setView(await api<StageView>(`/api/requests/${id}/stages/${pr}`));
    } catch (e) {
      setError(errorText(e));
    }
  }, [id, pr]);

  useEffect(() => {
    void load();
  }, [load]);

  function fail(e: unknown) {
    setResult({ kind: "error", text: errorText(e), reasons: e instanceof ApiError ? e.reasons : [] });
  }

  async function approve() {
    if (!view) return;
    setBusy(true);
    setResult(null);
    try {
      const r = await api<{ github_login: string }>(`/api/requests/${id}/stages/${pr}/approve`, {
        json: { head_sha: view.pr.head_sha, confirmed: true },
      });
      setResult({
        kind: "ok",
        text: `Approved on GitHub as ${r.github_login}. AISDLC will merge this PR and start the next stage.`,
      });
      setConfirmOpen(false);
      await load();
    } catch (e) {
      setConfirmOpen(false);
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  async function requestChanges() {
    setResult(null);
    try {
      const r = await api<{ github_login: string }>(`/api/requests/${id}/stages/${pr}/request-changes`, {
        json: { notes },
      });
      setResult({ kind: "ok", text: `Posted “/agent revise …” as ${r.github_login}.` });
      setNotes("");
    } catch (e) {
      fail(e);
    }
  }

  async function runCommand() {
    setResult(null);
    try {
      const r = await api<{ github_login: string; command: string }>(`/api/requests/${id}/commands`, {
        json: { command, pr_number: Number(pr) },
      });
      setResult({ kind: "ok", text: `Posted “${r.command}” as ${r.github_login}.` });
    } catch (e) {
      fail(e);
    }
  }

  if (!view) return error ? <Alert kind="error">{error}</Alert> : <Loading />;
  const pc = view.precheck;
  const open = view.pr.state === "open";
  const reviewer = isReviewer(me);

  return (
    <>
      <p>
        <Link to={`/requests/${id}`}>← Back to request</Link>
      </p>
      <h1>
        {view.stage.toUpperCase()} review · PR #{view.pr.number}
      </h1>
      <p>
        <a href={view.pr.url} target="_blank" rel="noreferrer">
          Open on GitHub
        </a>{" "}
        · state <strong>{view.pr.state}</strong> · opened by {view.pr.author}
      </p>
      <div aria-live="polite">
        {result && (
          <Alert kind={result.kind}>
            {result.text}
            {result.reasons && result.reasons.length > 0 && (
              <ul>
                {result.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            )}
          </Alert>
        )}
      </div>

      <div className="grid-2" style={{ gridTemplateColumns: "minmax(0, 2fr) minmax(260px, 1fr)" }}>
        <div>
          <div className="tabs" role="tablist" aria-label="Review material">
            {(
              [
                ["artifact", "Artifact"],
                ["diff", `Diff (${view.files.length})`],
                ["qc", "QC scorecard"],
                ["model", "Model decision"],
              ] as [Tab, string][]
            ).map(([t, label]) => (
              <button
                key={t}
                type="button"
                role="tab"
                id={`tab-${t}`}
                aria-selected={tab === t}
                aria-controls={`panel-${t}`}
                onClick={() => setTab(t)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="card" role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
            {tab === "artifact" &&
              (view.artifact.markdown ? (
                <>
                  <p className="muted">{view.artifact.path}</p>
                  <Markdown source={view.artifact.markdown} />
                </>
              ) : (
                <p className="muted">No Markdown artifact found in this PR. See the diff.</p>
              ))}
            {tab === "diff" &&
              view.files.map((f) => (
                <details key={f.filename} open={view.files.length <= 3}>
                  <summary>
                    {f.filename}{" "}
                    <span className="muted">
                      {f.status} +{f.additions} −{f.deletions}
                    </span>
                  </summary>
                  <Diff patch={f.patch} />
                </details>
              ))}
            {tab === "qc" && (
              <>
                <p>
                  QC: <strong>{view.summary.qc_status || "N/A"}</strong> {view.summary.qc_score ?? ""}
                  {view.summary.retries && ` · retries ${view.summary.retries}`}
                </p>
                {view.summary.diagnosis && <p>Diagnosis: {view.summary.diagnosis}</p>}
                {view.quality_report.markdown ? (
                  <Markdown source={view.quality_report.markdown} />
                ) : (
                  <p className="muted">No quality report file in this PR.</p>
                )}
              </>
            )}
            {tab === "model" && (
              <dl>
                <dt>Recommended model</dt>
                <dd>{view.summary.recommended_model || "N/A"}</dd>
                <dt>Selected model</dt>
                <dd>{view.summary.selected_model || "N/A"}</dd>
                <dt>Readiness</dt>
                <dd>{view.summary.readiness || "N/A"}</dd>
                <dt>Assumptions</dt>
                <dd>{view.summary.assumptions || "none"}</dd>
                <dt>Run</dt>
                <dd>{view.summary.run_id || "N/A"}</dd>
              </dl>
            )}
          </div>
        </div>

        <aside aria-labelledby="decide-h">
          <div className="card">
            <h2 id="decide-h">Your decision</h2>
            {!reviewer && <Alert kind="info">Reviewing needs the Reviewer role in the portal.</Alert>}
            {reviewer && view.github_link && !view.github_link.connected && (
              <Alert kind="info">
                {view.github_link.reason} <a href="/auth/github/connect">Connect GitHub</a>
              </Alert>
            )}
            {reviewer && view.github_link?.connected && pc && (
              <>
                <p className="hint">Acting as GitHub user {view.github_link.login}.</p>
                <CheckList view={view} />
                {open && pc.can_approve ? (
                  <div className="actions">
                    <button type="button" onClick={() => setConfirmOpen(true)}>
                      Approve…
                    </button>
                  </div>
                ) : (
                  open && (
                    <Alert kind="warn" title="Approve is not available">
                      <ul>
                        {(pc.reasons.length ? pc.reasons : ["See the checks above."]).map((r, i) => (
                          <li key={i}>{r}</li>
                        ))}
                      </ul>
                    </Alert>
                  )
                )}
                {open && (
                  <>
                    <h3>Request changes</h3>
                    <label htmlFor="notes">What should change?</label>
                    <p className="hint">Posted as “/agent revise &lt;your notes&gt;”.</p>
                    <textarea
                      id="notes"
                      rows={4}
                      maxLength={4000}
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                    />
                    <div className="actions">
                      <button type="button" className="secondary" disabled={!notes.trim()} onClick={requestChanges}>
                        Request changes
                      </button>
                    </div>
                    <h3>Other commands</h3>
                    <label htmlFor="cmd">Command</label>
                    <select id="cmd" value={command} onChange={(e) => setCommand(e.target.value)}>
                      {COMMANDS.map((c) => (
                        <option key={c.value} value={c.value}>
                          {c.label} (/agent {c.value})
                        </option>
                      ))}
                    </select>
                    <div className="actions">
                      <button type="button" className="secondary" onClick={runCommand}>
                        Send command
                      </button>
                    </div>
                  </>
                )}
              </>
            )}
            {view.reviews.length > 0 && (
              <>
                <h3>Reviews on GitHub</h3>
                <ul>
                  {view.reviews.map((r, i) => (
                    <li key={i}>
                      {r.user}: {r.state}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        </aside>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title={`Approve the ${view.stage.toUpperCase()}?`}
        confirmLabel="Approve on GitHub"
        confirmDisabled={!reviewed}
        busy={busy}
        onConfirm={approve}
        onCancel={() => setConfirmOpen(false)}
      >
        <p>{view.approve_confirmation}</p>
        <p>
          QC: <strong>{view.summary.qc_status || "N/A"}</strong> {view.summary.qc_score ?? ""} · {view.files.length}{" "}
          changed file(s)
        </p>
        <label>
          <input type="checkbox" checked={reviewed} onChange={(e) => setReviewed(e.target.checked)} /> I have reviewed
          the artifact, the diff and the QC scorecard.
        </label>
      </ConfirmDialog>
    </>
  );
}
