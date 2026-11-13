import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError, errorText } from "../api";
import { isReviewer, useMe } from "../App";
import { Alert, Loading, StatusBadge, formatBytes, formatDate } from "../components/ui";
import type { AuditRow, RequestDetail } from "../types";

const STAGES = ["brd", "prd", "epic", "architecture", "nfr", "task", "code"];

function Timeline({ detail }: { detail: RequestDetail }) {
  const stages = detail.snapshot.stages ?? [];
  const merged = new Set(stages.filter((s) => s.state === "merged").map((s) => s.agent));
  const current = detail.snapshot.open_stage_pr ? detail.stage : "";
  return (
    <ol className="timeline" aria-label="AISDLC stages">
      {STAGES.map((s) => (
        <li
          key={s}
          className={merged.has(s) ? "done" : s === current ? "current" : ""}
          aria-current={s === current ? "step" : undefined}
        >
          {s.toUpperCase()}
          {merged.has(s) ? " ✓" : ""}
          <span className="sr-only">{merged.has(s) ? " approved" : s === current ? " in review" : ""}</span>
        </li>
      ))}
    </ol>
  );
}

function AnswerForm({ detail, onDone }: { detail: RequestDetail; onDone: (message: string) => void }) {
  const { me } = useMe();
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const questions = detail.snapshot.questions ?? [];

  async function send() {
    setBusy(true);
    setError("");
    try {
      const r = await api<{ github_login: string }>(`/api/requests/${detail.id}/answer`, { json: { answer } });
      setAnswer("");
      onDone(`Posted to GitHub as ${r.github_login}. AISDLC will resume.`);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card" aria-labelledby="questions-h">
      <h2 id="questions-h">AISDLC needs more information</h2>
      <ul>
        {questions.map((q, i) => (
          <li key={i}>{q}</li>
        ))}
      </ul>
      {error && <Alert kind="error">{error}</Alert>}
      {!me.github.connected ? (
        <Alert kind="info">
          Your answer is posted with your own GitHub account. <a href="/auth/github/connect">Connect GitHub</a> to
          answer here.
        </Alert>
      ) : (
        <>
          <label htmlFor="answer">Your answer</label>
          <p className="hint">
            Posted as a comment by <strong>{me.github.login}</strong>. Do not start with “/”.
          </p>
          <textarea id="answer" rows={6} value={answer} onChange={(e) => setAnswer(e.target.value)} />
          <div className="actions">
            <button type="button" onClick={send} disabled={busy || !answer.trim()}>
              {busy ? "Posting…" : "Post answer"}
            </button>
          </div>
        </>
      )}
    </section>
  );
}

function ModelPanel({
  detail,
  models,
  onDone,
}: {
  detail: RequestDetail;
  models: string[];
  onDone: (message: string) => void;
}) {
  const [model, setModel] = useState("");
  const [reason, setReason] = useState("");
  const [msg, setMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const rec = detail.snapshot.model_pending?.recommended_model ?? "";

  async function send(command: "approve" | "select") {
    setMsg(null);
    try {
      const r = await api<{ github_login: string; command: string }>(`/api/requests/${detail.id}/model`, {
        json: { command, model, reason },
      });
      onDone(`Posted “${r.command}” as ${r.github_login}.`);
    } catch (e) {
      setMsg({ kind: "error", text: errorText(e) });
    }
  }

  return (
    <section className="card" aria-labelledby="model-h">
      <h2 id="model-h">Model confirmation</h2>
      <p>
        AISDLC recommends <strong>{rec || "a model"}</strong> for this stage. Confirming the model is separate from
        approving the artifact.
      </p>
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <div className="actions">
        <button type="button" onClick={() => send("approve")}>
          Use recommended model
        </button>
      </div>
      <div className="grid-2" style={{ marginTop: "1rem" }}>
        <div>
          <label htmlFor="model">Or choose another model</label>
          <select id="model" value={model} onChange={(e) => setModel(e.target.value)}>
            <option value="">Select…</option>
            {models.map((m) => (
              <option key={m}>{m}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="reason">Reason (required)</label>
          <input id="reason" value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)} />
        </div>
      </div>
      <div className="actions">
        <button type="button" className="secondary" disabled={!model || !reason.trim()} onClick={() => send("select")}>
          Select model
        </button>
      </div>
    </section>
  );
}

export function RequestDetailPage() {
  const { id = "" } = useParams();
  const { me } = useMe();
  const [detail, setDetail] = useState<RequestDetail | null>(null);
  const [audit, setAudit] = useState<AuditRow[]>([]);
  const [models, setModels] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [notFound, setNotFound] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  const load = useCallback(
    async (refresh = false) => {
      try {
        const d = refresh
          ? await api<RequestDetail>(`/api/requests/${id}/refresh`, { method: "POST" })
          : await api<RequestDetail>(`/api/requests/${id}`);
        setDetail((prev) => ({ ...d, is_requester: d.is_requester ?? prev?.is_requester ?? false }));
        setError("");
        api<{ entries: AuditRow[] }>(`/api/requests/${id}/audit`)
          .then((r) => setAudit(r.entries))
          .catch(() => undefined);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) setNotFound(true);
        else setError(errorText(e));
      }
    },
    [id],
  );

  useEffect(() => {
    void load();
    const t = window.setInterval(() => void load(), 15000);
    return () => window.clearInterval(t);
  }, [load]);

  useEffect(() => {
    if (detail?.snapshot.model_pending && isReviewer(me) && models.length === 0)
      api<{ models: string[] }>("/api/commands")
        .then((r) => setModels(r.models))
        .catch(() => undefined);
  }, [detail, me, models.length]);

  async function retry() {
    setBusy(true);
    try {
      setDetail({ ...(await api<RequestDetail>(`/api/requests/${id}/retry-submit`, { method: "POST" })) });
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  if (notFound) return <Alert kind="info">Request not found, or you do not have access to it.</Alert>;
  if (!detail) return error ? <Alert kind="error">{error}</Alert> : <Loading />;
  const snap = detail.snapshot;
  const canAnswer = detail.is_requester || isReviewer(me);

  return (
    <>
      <h1>{detail.title}</h1>
      <p>
        <StatusBadge status={detail.status} />{" "}
        {detail.issue_url && (
          <a href={detail.issue_url} target="_blank" rel="noreferrer">
            GitHub issue #{detail.issue_number}
          </a>
        )}{" "}
        <span className="muted">· {detail.id}</span>
      </p>
      <div aria-live="polite">
        {notice && <Alert kind="ok">{notice}</Alert>}
        {error && <Alert kind="error">{error}</Alert>}
      </div>
      {snap.sync_error && <Alert kind="warn">Status may be out of date: {snap.sync_error}</Alert>}

      {detail.status === "submit_failed" && (
        <Alert kind="error" title="The submission did not finish.">
          <p>{detail.error}</p>
          {detail.is_requester && (
            <button type="button" onClick={retry} disabled={busy}>
              {busy ? "Retrying…" : "Retry"}
            </button>
          )}
        </Alert>
      )}
      {detail.status === "queued" && (
        <Alert kind="info">Queued: AISDLC starts once CodeQL has passed for the current main commit.</Alert>
      )}
      {detail.status === "needs_attention" && (
        <Alert kind="warn" title="The stage paused after QC.">
          <ul>
            {(snap.paused_findings ?? []).map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </Alert>
      )}

      {detail.status === "awaiting_info" && canAnswer && (
        <AnswerForm
          detail={detail}
          onDone={(m) => {
            setNotice(m);
            void load();
          }}
        />
      )}
      {detail.status === "awaiting_model" && isReviewer(me) && (
        <ModelPanel
          detail={detail}
          models={models}
          onDone={(m) => {
            setNotice(m);
            void load();
          }}
        />
      )}

      <section className="card" aria-labelledby="stages-h">
        <h2 id="stages-h">Stages</h2>
        <Timeline detail={detail} />
        {(snap.stages ?? []).length === 0 ? (
          <p className="muted">No stage pull requests yet.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Stage</th>
                  <th scope="col">Pull request</th>
                  <th scope="col">State</th>
                  <th scope="col">QC</th>
                  <th scope="col">Model</th>
                  <th scope="col">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {(snap.stages ?? []).map((s) => (
                  <tr key={s.pr_number}>
                    <td>{s.agent.toUpperCase()}</td>
                    <td>
                      <a href={s.url} target="_blank" rel="noreferrer">
                        #{s.pr_number}
                      </a>
                    </td>
                    <td>{s.state}</td>
                    <td>
                      {s.summary.qc_status || "—"} {s.summary.qc_score ?? ""}
                    </td>
                    <td>{s.summary.selected_model || "—"}</td>
                    <td>
                      <Link to={`/requests/${detail.id}/stages/${s.pr_number}`}>
                        {s.state === "open" ? "Review" : "View"}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="actions">
          <button type="button" className="secondary" onClick={() => load(true)}>
            Refresh from GitHub
          </button>
          <span className="muted">Last synced {formatDate(detail.last_synced_at)}</span>
        </div>
      </section>

      <div className="grid-2">
        <section className="card" aria-labelledby="labels-h">
          <h2 id="labels-h">GitHub</h2>
          <p>
            Labels:{" "}
            {(snap.labels ?? []).length
              ? (snap.labels ?? []).map((l) => (
                  <span key={l} className="badge">
                    {l}{" "}
                  </span>
                ))
              : "none"}
          </p>
          {snap.latest_run && (
            <p>
              Latest run:{" "}
              <a href={snap.latest_run.url} target="_blank" rel="noreferrer">
                {snap.latest_run.status} {snap.latest_run.conclusion ?? ""}
              </a>
            </p>
          )}
          {detail.overflow_parts.total > 0 && (
            <p>
              Continuation comments: {detail.overflow_parts.posted} of {detail.overflow_parts.total}
            </p>
          )}
          {detail.overflow_branch && (
            <p>
              Intake branch: <code>{detail.overflow_branch}</code>
            </p>
          )}
        </section>
        <section className="card" aria-labelledby="files-h">
          <h2 id="files-h">Documents</h2>
          {detail.files.length === 0 ? (
            <p className="muted">None.</p>
          ) : (
            <ul>
              {detail.files.map((f) => (
                <li key={f.filename}>
                  {f.filename} <span className="muted">({formatBytes(f.size)})</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="card" aria-labelledby="audit-h">
        <h2 id="audit-h">Activity</h2>
        {audit.length === 0 ? (
          <p className="muted">No activity yet.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">When</th>
                  <th scope="col">Who</th>
                  <th scope="col">Action</th>
                  <th scope="col">Target</th>
                  <th scope="col">Result</th>
                </tr>
              </thead>
              <tbody>
                {audit.map((a, i) => (
                  <tr key={i}>
                    <td className="nowrap">{formatDate(a.ts)}</td>
                    <td>
                      {a.github_login} <span className="muted">({a.identity})</span>
                    </td>
                    <td>{a.action}</td>
                    <td>{a.target}</td>
                    <td>
                      {a.outcome}
                      {a.github_status ? ` (${a.github_status})` : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
