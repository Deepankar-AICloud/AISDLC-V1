import { useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorText } from "../api";
import { isRequester, useMe } from "../App";
import { Dropzone, type LocalFile } from "../components/Dropzone";
import { Alert, formatBytes } from "../components/ui";
import type { Preview, RequestDetail } from "../types";

const FIELDS: { key: string; label: string; guidance: string; multiline: boolean }[] = [
  { key: "title", label: "Title", guidance: "A short name for the requirement.", multiline: false },
  {
    key: "business_problem",
    label: "Business problem",
    guidance: "What is not working today, and for whom?",
    multiline: true,
  },
  {
    key: "objective",
    label: "Objective",
    guidance: "What outcome should the change achieve? How will you know it worked?",
    multiline: true,
  },
  {
    key: "stakeholders",
    label: "Stakeholders",
    guidance: "Who is affected or needs to approve (roles or teams)?",
    multiline: true,
  },
  { key: "scope", label: "Scope", guidance: "What is included, and what is out of scope?", multiline: true },
  {
    key: "constraints",
    label: "Constraints",
    guidance: "Deadlines, compliance, policy, technology or budget limits.",
    multiline: true,
  },
  {
    key: "target_repository",
    label: "Target repository",
    guidance: "Optional, for example org/repo.",
    multiline: false,
  },
];

type Edit = { include: boolean; text: string };

export function NewRequestPage() {
  const { me } = useMe();
  const navigate = useNavigate();
  const [fields, setFields] = useState<Record<string, string>>({});
  const [pasted, setPasted] = useState("");
  const [files, setFiles] = useState<LocalFile[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [edits, setEdits] = useState<Record<string, Edit>>({});
  const [busy, setBusy] = useState<"" | "preview" | "submit">("");
  const [error, setError] = useState("");
  const idemKey = useRef<string>("");
  const previewHeading = useRef<HTMLHeadingElement>(null);

  const cfg = me.config;
  const blocked = files.some((f) => f.problem);
  const filled = FIELDS.filter((f) => f.key !== "title" && (fields[f.key] ?? "").trim()).length;
  const hasContent = pasted.trim() || files.length || filled;

  const totalBytes = useMemo(() => files.reduce((n, f) => n + f.file.size, 0), [files]);

  if (!isRequester(me))
    return <Alert kind="info">Submitting requirements needs the Requester role in the portal.</Alert>;

  async function runPreview() {
    setError("");
    setBusy("preview");
    try {
      const form = new FormData();
      form.set("fields", JSON.stringify(fields));
      form.set("pasted_text", pasted);
      files.forEach((f) => form.append("files", f.file, f.file.name));
      const p = await api<Preview>("/api/intake/preview", { form });
      setPreview(p);
      setEdits(Object.fromEntries(p.files.map((f) => [f.id, { include: !f.error, text: f.text }])));
      idemKey.current = crypto.randomUUID();
      setTimeout(() => previewHeading.current?.focus(), 0);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy("");
    }
  }

  async function submit() {
    if (!preview || busy) return;
    setError("");
    setBusy("submit");
    try {
      const body = {
        draft_id: preview.draft_id,
        fields,
        pasted_text: pasted,
        files: preview.files.map((f) => ({
          id: f.id,
          include: edits[f.id]?.include ?? false,
          text: edits[f.id]?.text ?? f.text,
        })),
      };
      const r = await api<{ request: RequestDetail }>("/api/requests", {
        json: body,
        headers: { "Idempotency-Key": idemKey.current },
      });
      navigate(`/requests/${r.request.id}`);
    } catch (e) {
      setError(errorText(e));
      setBusy("");
    }
  }

  return (
    <>
      <h1>New requirement</h1>
      <Alert kind="warn" title="Before you start">
        {cfg.notice}
      </Alert>
      {error && <Alert kind="error">{error}</Alert>}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void runPreview();
        }}
      >
        <div className="card">
          <div className="field">
            <label htmlFor="pasted">Requirement text</label>
            <p className="hint" id="pasted-hint">
              Paste the requirement as you have it. AISDLC will ask for anything it needs.
            </p>
            <textarea
              id="pasted"
              className="big"
              aria-describedby="pasted-hint"
              value={pasted}
              maxLength={cfg.max_pasted_chars}
              onChange={(e) => {
                setPasted(e.target.value);
                setPreview(null);
              }}
            />
          </div>
          <h2>Supporting documents</h2>
          <Dropzone
            files={files}
            onChange={(f) => {
              setFiles(f);
              setPreview(null);
            }}
            allowed={cfg.allowed_extensions}
            maxFiles={cfg.max_files}
            maxMb={cfg.max_file_mb}
          />
          {totalBytes > cfg.max_total_mb * 1024 * 1024 && (
            <Alert kind="error">
              Total size {formatBytes(totalBytes)} is over the {cfg.max_total_mb} MB limit.
            </Alert>
          )}
        </div>

        <details className="card">
          <summary>Structured fields (optional) · {filled} of 5 filled</summary>
          <p className="hint">
            These mirror the AISDLC readiness check: business problem, objective and stakeholders are needed before the
            BRD is generated; scope and constraints are recommended. Missing items are fine.
          </p>
          {FIELDS.map((f) => (
            <div className="field" key={f.key}>
              <label htmlFor={`f-${f.key}`}>{f.label}</label>
              <p className="hint" id={`h-${f.key}`}>
                {f.guidance}
              </p>
              {f.multiline ? (
                <textarea
                  id={`f-${f.key}`}
                  rows={3}
                  maxLength={4000}
                  aria-describedby={`h-${f.key}`}
                  value={fields[f.key] ?? ""}
                  onChange={(e) => {
                    setFields({ ...fields, [f.key]: e.target.value });
                    setPreview(null);
                  }}
                />
              ) : (
                <input
                  id={`f-${f.key}`}
                  maxLength={200}
                  aria-describedby={`h-${f.key}`}
                  value={fields[f.key] ?? ""}
                  onChange={(e) => {
                    setFields({ ...fields, [f.key]: e.target.value });
                    setPreview(null);
                  }}
                />
              )}
            </div>
          ))}
        </details>

        <div className="actions">
          <button type="submit" disabled={!hasContent || blocked || busy !== ""}>
            {busy === "preview" ? "Extracting…" : "Preview"}
          </button>
          {blocked && <span className="muted">Remove the files marked with a problem first.</span>}
        </div>
      </form>

      {preview && (
        <section aria-labelledby="preview-heading">
          <h2 id="preview-heading" ref={previewHeading} tabIndex={-1}>
            Preview
          </h2>
          <div className={`alert ${preview.completeness.missing_mandatory.length ? "warn" : "ok"}`} role="status">
            <strong>Completeness: </strong>
            {preview.completeness.hint}
            <ul>
              {preview.completeness.items.map((i) => (
                <li key={i.key}>
                  {i.detected ? "✓" : "○"} {i.label}
                  {i.mandatory ? "" : " (recommended)"}
                  {!i.detected && <span className="muted"> — {i.guidance}</span>}
                </li>
              ))}
            </ul>
          </div>

          <h3>Documents</h3>
          {preview.files.length === 0 && <p className="muted">No documents attached.</p>}
          {preview.files.map((f) => {
            const edit = edits[f.id];
            return (
              <details key={f.id} open={!!f.error}>
                <summary>
                  {f.filename}{" "}
                  {f.error ? (
                    <span className="badge danger">{f.error.message}</span>
                  ) : (
                    <span className="muted">
                      {f.kind.toUpperCase()}
                      {f.pages != null && ` · ${f.pages} pages`}
                      {f.slides != null && ` · ${f.slides} slides`}
                      {f.sheets != null && ` · ${f.sheets} sheets`} · {f.chars.toLocaleString()} characters
                      {!edit?.include && " · removed"}
                    </span>
                  )}
                  {f.injection_flags.length > 0 && <span className="badge warn">Check flagged phrases</span>}
                </summary>
                {!f.error && edit && (
                  <>
                    {f.warnings.length > 0 && (
                      <Alert kind="warn" title="Extraction notes">
                        <ul>
                          {f.warnings.map((w, i) => (
                            <li key={i}>{w}</li>
                          ))}
                        </ul>
                      </Alert>
                    )}
                    {f.injection_flags.length > 0 && (
                      <Alert kind="warn" title="Phrases that look like instructions to an AI">
                        <p>They were left unchanged. AISDLC treats document text as data, but please check them.</p>
                        <ul>
                          {f.injection_flags.map((x, i) => (
                            <li key={i}>
                              Line {x.line} ({x.phrase}): <q>{x.snippet}</q>
                            </li>
                          ))}
                        </ul>
                      </Alert>
                    )}
                    <label>
                      <input
                        type="checkbox"
                        checked={edit.include}
                        onChange={(e) => setEdits({ ...edits, [f.id]: { ...edit, include: e.target.checked } })}
                      />{" "}
                      Include this file
                    </label>
                    <label htmlFor={`t-${f.id}`}>Extracted text (you can edit it)</label>
                    <textarea
                      id={`t-${f.id}`}
                      className="mono"
                      rows={10}
                      value={edit.text}
                      disabled={!edit.include}
                      onChange={(e) => setEdits({ ...edits, [f.id]: { ...edit, text: e.target.value } })}
                    />
                  </>
                )}
              </details>
            );
          })}

          <h3>GitHub issue</h3>
          {preview.plan_error ? (
            <Alert kind="error">{preview.plan_error}</Alert>
          ) : (
            <>
              <p>
                Title: <strong>{preview.issue.title}</strong> · repository {preview.repository.full_name}
              </p>
              {(preview.issue.overflow_comments ?? 0) > 0 && (
                <Alert kind="info">
                  The text is longer than one GitHub issue allows, so {preview.issue.overflow_comments} continuation
                  comment(s) will be posted before AISDLC starts.
                  {preview.issue.uses_branch && " Full text and original files go to a separate intake branch."}
                </Alert>
              )}
              <details>
                <summary>Issue body preview (before your edits)</summary>
                <pre className="body-preview">{preview.issue.body}</pre>
              </details>
              <p className="hint">
                After you submit, the portal creates the issue, then adds the <code>sdlc:start</code> label to start
                AISDLC.
              </p>
            </>
          )}
          <div className="actions">
            <button type="button" onClick={submit} disabled={busy !== "" || !!preview.plan_error}>
              {busy === "submit" ? "Submitting…" : "Submit to AISDLC"}
            </button>
            <button type="button" className="secondary" onClick={() => setPreview(null)} disabled={busy !== ""}>
              Back to editing
            </button>
          </div>
        </section>
      )}
    </>
  );
}
