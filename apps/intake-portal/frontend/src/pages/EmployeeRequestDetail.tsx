import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { api, errorText } from "../api";
import { useMe } from "../App";
import { Alert, Loading, formatDate } from "../components/ui";
import type { EmployeeRequest } from "../types";
import { getTrackingToken } from "../trackingAccess";

const STATUS: Record<EmployeeRequest["status"], { label: string; icon: string; tone: string }> = {
  submitted: { label: "Submitted", icon: "✓", tone: "" },
  under_review: { label: "Under review", icon: "◷", tone: "warn" },
  more_information_required: { label: "More information required", icon: "!", tone: "warn" },
  approved: { label: "Approved", icon: "✓", tone: "ok" },
  in_progress: { label: "In progress", icon: "◷", tone: "" },
  completed: { label: "Completed", icon: "✓", tone: "ok" },
  rejected: { label: "Not approved", icon: "×", tone: "danger" },
};

function EmployeeStatus({ status }: { status: EmployeeRequest["status"] }) {
  const item = STATUS[status];
  return (
    <span className={`badge employee-status ${item.tone}`}>
      <span aria-hidden="true">{item.icon}</span> {item.label}
    </span>
  );
}

export function EmployeeRequestDetailPage() {
  const { id = "" } = useParams();
  const { me } = useMe();
  const location = useLocation();
  const routeState = location.state as
    | { request?: EmployeeRequest; tracking_token?: string; tracking_saved?: boolean }
    | null;
  const initialRequest = routeState?.request ?? null;
  const openMode = me.config.auth_mode === "open";
  const sharedSignIn = !openMode && me.user.sign_in === "password";
  const [detail, setDetail] = useState<EmployeeRequest | null>(() => (sharedSignIn ? initialRequest : null));
  const [trackingToken, setTrackingToken] = useState(() => routeState?.tracking_token ?? "");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [answer, setAnswer] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const token = trackingToken || (openMode ? getTrackingToken(id) : "");
      if (openMode && !token) throw new Error("This browser does not have the private tracking access for this request.");
      if (token) setTrackingToken(token);
      const request = await api<EmployeeRequest>(`/api/employee/requests/${id}`, {
        headers: token ? { "X-Request-Access": token } : undefined,
      });
      setDetail(request);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : errorText(e));
    }
  }, [id, openMode, trackingToken]);

  useEffect(() => {
    if (sharedSignIn) return;
    void load();
    const timer = window.setInterval(() => void load(), 30000);
    return () => window.clearInterval(timer);
  }, [load, sharedSignIn]);

  const fileError = useMemo(() => {
    if (files.length > me.config.max_files) return `Choose no more than ${me.config.max_files} files.`;
    const total = files.reduce((sum, file) => sum + file.size, 0);
    const maxFile = me.config.max_file_mb * 1024 * 1024;
    if (files.some((file) => file.size > maxFile))
      return `Each file must be no larger than ${me.config.max_file_mb} MB.`;
    if (total > me.config.max_total_mb * 1024 * 1024)
      return `The total upload must be no larger than ${me.config.max_total_mb} MB.`;
    const extensions = me.config.allowed_extensions.map((extension) => extension.toLowerCase());
    const invalid = files.find((file) => {
      const dot = file.name.lastIndexOf(".");
      return dot < 0 || !extensions.includes(file.name.slice(dot).toLowerCase());
    });
    if (invalid) return `${invalid.name} is not an allowed file type.`;
    return "";
  }, [files, me.config.allowed_extensions, me.config.max_file_mb, me.config.max_files, me.config.max_total_mb]);

  async function sendInformation(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || fileError || (!answer.trim() && files.length === 0)) return;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const form = new FormData();
      form.set("answer", answer);
      files.forEach((file) => form.append("files", file, file.name));
      await api<{ submitted: boolean }>(`/api/employee/requests/${id}/information`, {
        form,
        headers: trackingToken ? { "X-Request-Access": trackingToken } : undefined,
      });
      setAnswer("");
      setFiles([]);
      await load();
      setSuccess("Thanks—your information was sent to the IT team.");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  async function retrySubmission() {
    setBusy(true);
    setError("");
    try {
      await api<EmployeeRequest>(`/api/requests/${id}/retry-submit`, {
        method: "POST",
        headers: trackingToken ? { "X-Request-Access": trackingToken } : undefined,
      });
      await load();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  if (!detail && !error && !sharedSignIn) return <Loading />;
  if (!detail && sharedSignIn) {
    return (
      <>
        <h1>Request tracking</h1>
        <Alert kind="warn" title="Personal sign-in is required">
          This portal uses shared sign-in, so it cannot securely identify which requests belong to you. Ask your
          administrator to enable individual Microsoft Entra sign-in.
        </Alert>
        <Link to="/requests">Back to requests</Link>
      </>
    );
  }
  if (!detail && error)
    return (
      <Alert kind="error" title="We could not load this request.">
        {error}
      </Alert>
    );

  const request = detail!;
  const status = STATUS[request.status];

  return (
    <>
      <div className="employee-page-heading">
        <div>
          <Link to="/requests">← My requests</Link>
          <h1>{request.title}</h1>
        </div>
        <EmployeeStatus status={request.status} />
      </div>

      {sharedSignIn && (
        <Alert kind="warn" title="Live tracking needs individual sign-in">
          This portal uses shared sign-in. Your request was received, but personal tracking is unavailable until your
          administrator enables individual Microsoft Entra sign-in.
        </Alert>
      )}
      {openMode && routeState?.tracking_saved === false && (
        <Alert kind="warn" title="Tracking access could not be saved in this browser">
          Keep this page open to continue tracking. If you leave or refresh it, you may need to submit the request
          again to restore access.
        </Alert>
      )}
      {error && <Alert kind="error">{error}</Alert>}
      {success && <Alert kind="ok">{success}</Alert>}

      <section className="employee-confirmation card" aria-labelledby="confirmation-heading">
        <div className="employee-confirmation-icon" aria-hidden="true">
          {status.icon}
        </div>
        <div>
          <h2 id="confirmation-heading">
            {request.can_retry_submission ? "Your request is saved" : "Your request has been submitted"}
          </h2>
          <p>
            {request.can_retry_submission
              ? "We could not finish sending it to the review team yet."
              : "We’ll keep you updated as it moves through review."}
          </p>
          <dl className="employee-summary">
            <div>
              <dt>Request ID</dt>
              <dd>{request.id}</dd>
            </div>
            <div>
              <dt>Submitted</dt>
              <dd>{formatDate(request.submitted_at)}</dd>
            </div>
          </dl>
          {request.can_retry_submission && !sharedSignIn && (
            <button type="button" onClick={retrySubmission} disabled={busy}>
              {busy ? "Retrying…" : "Retry submission"}
            </button>
          )}
        </div>
      </section>

      <div className="employee-grid">
        <section className="card" aria-labelledby="status-heading">
          <h2 id="status-heading">Current status</h2>
          <p className="employee-current-status">
            <EmployeeStatus status={request.status} />
          </p>
          <ol className="employee-progress" aria-label="Request progress">
            {request.progress.map((step) => (
              <li key={step.id} className={`progress-${step.state}`}>
                <span className="progress-marker" aria-hidden="true">
                  {step.state === "completed" ? "✓" : step.state === "rejected" ? "×" : ""}
                </span>
                <span>{step.label}</span>
                <span className="sr-only">
                  {step.state === "completed"
                    ? "Completed"
                    : step.state === "current"
                      ? "Current stage"
                      : step.state === "delayed"
                        ? "Waiting for information"
                        : step.state === "rejected"
                          ? "Not approved"
                          : "Not started"}
                </span>
              </li>
            ))}
          </ol>
        </section>

        <section className="card" aria-labelledby="update-heading">
          <h2 id="update-heading">Latest update</h2>
          <p className="employee-update">{request.latest_update.message}</p>
          <p className="muted">
            {request.latest_update.from} · {formatDate(request.latest_update.updated_at)}
          </p>
          <dl className="employee-meta">
            <div>
              <dt>Reviewer</dt>
              <dd>{request.assigned_reviewer ?? "Not assigned yet"}</dd>
            </div>
            <div>
              <dt>Expected completion</dt>
              <dd>
                {request.expected_completion_at ? formatDate(request.expected_completion_at) : "Not available yet"}
              </dd>
            </div>
          </dl>
        </section>
      </div>

      <section className="card" aria-labelledby="action-heading">
        <h2 id="action-heading">Action required</h2>
        {request.action_required.required ? (
          sharedSignIn ? (
            <Alert kind="warn" title="The IT team needs more information">
              Personal sign-in is required to send a response. Ask your administrator to enable individual Microsoft
              Entra sign-in.
            </Alert>
          ) : (
            <>
              <Alert kind="warn" title="We need a little more information">
                <p>Please answer the questions below so the review can continue.</p>
                {request.action_required.questions.length > 0 && (
                  <ul>
                    {request.action_required.questions.map((question, index) => (
                      <li key={index}>{question}</li>
                    ))}
                  </ul>
                )}
              </Alert>
              {openMode ? (
                <Alert kind="info">
                  Follow-up responses must be attributed to an individual GitHub account. To keep using the portal
                  without signing in, contact IT and include your request ID.
                </Alert>
              ) : !me.github.connected ? (
                <Alert kind="info">
                  Connect your GitHub account to send your response securely.{" "}
                  <a href="/auth/github/connect">Connect GitHub</a>
                </Alert>
              ) : (
                <form onSubmit={sendInformation}>
                  <label htmlFor="employee-answer">Your response</label>
                  <textarea
                    id="employee-answer"
                    rows={5}
                    value={answer}
                    onChange={(event) => setAnswer(event.target.value)}
                  />
                  <div className="field">
                    <label htmlFor="employee-files">Supporting documents (optional)</label>
                    <input
                      id="employee-files"
                      type="file"
                      multiple
                      accept={me.config.allowed_extensions.join(",")}
                      onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
                    />
                    <p className="hint">
                      Up to {me.config.max_files} files, {me.config.max_file_mb} MB each and {me.config.max_total_mb} MB
                      total.
                    </p>
                    {files.length > 0 && (
                      <ul>
                        {files.map((file) => (
                          <li key={`${file.name}-${file.size}-${file.lastModified}`}>{file.name}</li>
                        ))}
                      </ul>
                    )}
                    {fileError && (
                      <p className="field-error" role="alert">
                        {fileError}
                      </p>
                    )}
                  </div>
                  <button type="submit" disabled={busy || !!fileError || (!answer.trim() && files.length === 0)}>
                    {busy ? "Sending…" : "Provide information"}
                  </button>
                </form>
              )}
            </>
          )
        ) : (
          <p className="employee-no-action">✓ No action required from you at this moment.</p>
        )}
      </section>

      <section className="card" aria-labelledby="details-heading">
        <h2 id="details-heading">Request details</h2>
        <dl className="employee-details">
          <div>
            <dt>Request ID</dt>
            <dd>{request.id}</dd>
          </div>
          <div>
            <dt>Title</dt>
            <dd>{request.title}</dd>
          </div>
          <div>
            <dt>Problem description</dt>
            <dd>{request.problem || "Not provided"}</dd>
          </div>
          <div>
            <dt>Objective</dt>
            <dd>{request.objective || "Not provided"}</dd>
          </div>
          <div>
            <dt>Submitted</dt>
            <dd>{formatDate(request.submitted_at)}</dd>
          </div>
          <div>
            <dt>Current status</dt>
            <dd>{status.label}</dd>
          </div>
        </dl>
      </section>
    </>
  );
}
