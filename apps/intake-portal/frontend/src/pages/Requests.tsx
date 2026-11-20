import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorText } from "../api";
import { isRequester, isReviewer, useMe } from "../App";
import { Alert, Empty, Loading, StatusBadge, formatDate } from "../components/ui";
import type { EmployeeRequest, RequestSummary } from "../types";
import { readTrackingAccess } from "../trackingAccess";

const EMPLOYEE_STATUSES: { value: EmployeeRequest["status"] | ""; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "submitted", label: "Submitted" },
  { value: "under_review", label: "Under review" },
  { value: "more_information_required", label: "More information required" },
  { value: "approved", label: "Approved" },
  { value: "in_progress", label: "In progress" },
  { value: "completed", label: "Completed" },
  { value: "rejected", label: "Not approved" },
];

function EmployeeStatus({ status }: { status: EmployeeRequest["status"] }) {
  const labels: Record<EmployeeRequest["status"], string> = {
    submitted: "Submitted",
    under_review: "Under review",
    more_information_required: "More information required",
    approved: "Approved",
    in_progress: "In progress",
    completed: "Completed",
    rejected: "Not approved",
  };
  const tone =
    status === "completed" || status === "approved"
      ? "ok"
      : status === "more_information_required" || status === "under_review"
        ? "warn"
        : status === "rejected"
          ? "danger"
          : "";
  return <span className={`badge ${tone}`}>{labels[status]}</span>;
}

function MyRequests() {
  const { me } = useMe();
  const [rows, setRows] = useState<EmployeeRequest[] | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<EmployeeRequest["status"] | "">("");
  const openMode = me.config.auth_mode === "open";
  const sharedSignIn = !openMode && me.user.sign_in === "password";

  useEffect(() => {
    if (sharedSignIn) return;
    if (openMode) {
      try {
        const access = readTrackingAccess();
        if (!access.length) {
          setRows([]);
          return;
        }
        void Promise.all(
          access.map(({ id, token }) =>
            api<EmployeeRequest>(`/api/employee/requests/${id}`, {
              headers: { "X-Request-Access": token },
            }),
          ),
        )
          .then(setRows)
          .catch((e) => setError(errorText(e)));
      } catch (e) {
        setError(e instanceof Error ? e.message : errorText(e));
      }
      return;
    }
    api<{ requests: EmployeeRequest[] }>("/api/employee/requests")
      .then((response) => setRows(response.requests))
      .catch((e) => setError(errorText(e)));
  }, [openMode, sharedSignIn]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (rows ?? []).filter(
      (request) =>
        (!status || request.status === status) &&
        (!needle || request.title.toLowerCase().includes(needle) || request.id.toLowerCase().includes(needle)),
    );
  }, [query, rows, status]);

  return (
    <section aria-labelledby="my-requests-heading">
      <h2 id="my-requests-heading">My requests</h2>
      {sharedSignIn && (
        <Alert kind="warn" title="Personal request history is unavailable">
          This portal uses shared sign-in, so it cannot securely identify which requests belong to you. Ask your
          administrator to enable individual Microsoft Entra sign-in.
        </Alert>
      )}
      {openMode && (
        <Alert kind="info">
          Your anonymous request list is saved in this browser. Other visitors cannot see your requests without their
          private tracking access.
        </Alert>
      )}
      {error && <Alert kind="error">{error}</Alert>}
      {!sharedSignIn && !rows && !error && <Loading />}
      {!sharedSignIn && rows && (
        <>
          <div className="employee-filters">
            <div className="field">
              <label htmlFor="request-search">Search requests</label>
              <input
                id="request-search"
                type="search"
                placeholder="Search by title or request ID"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="request-status">Filter by status</label>
              <select
                id="request-status"
                value={status}
                onChange={(event) => setStatus(event.target.value as EmployeeRequest["status"] | "")}
              >
                {EMPLOYEE_STATUSES.map((option) => (
                  <option value={option.value} key={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          {rows.length === 0 ? (
            <Empty>
              No requests yet. <Link to="/new">Submit a new request</Link>.
            </Empty>
          ) : filtered.length === 0 ? (
            <Empty>No requests match your search and status filter.</Empty>
          ) : (
            <div className="employee-request-list">
              {filtered.map((request) => (
                <article className="employee-request-card" key={request.id}>
                  <div className="employee-request-card-heading">
                    <h3>
                      <Link to={`/my-requests/${request.id}`}>{request.title}</Link>
                    </h3>
                    <EmployeeStatus status={request.status} />
                  </div>
                  <p className="muted">{request.id}</p>
                  <dl className="employee-request-card-meta">
                    <div>
                      <dt>Submitted</dt>
                      <dd>{formatDate(request.submitted_at)}</dd>
                    </div>
                    <div>
                      <dt>Last updated</dt>
                      <dd>{formatDate(request.last_updated_at)}</dd>
                    </div>
                  </dl>
                  <Link className="button secondary" to={`/my-requests/${request.id}`}>
                    View details
                  </Link>
                </article>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}

function AssignedRequests() {
  const [rows, setRows] = useState<RequestSummary[] | null>(null);
  const [hint, setHint] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ requests: RequestSummary[]; hint?: string }>("/api/requests?scope=assigned")
      .then((response) => {
        setRows(response.requests);
        setHint(response.hint ?? "");
      })
      .catch((e) => setError(errorText(e)));
  }, []);

  return (
    <section aria-labelledby="assigned-heading">
      <h2 id="assigned-heading">Assigned to me for review</h2>
      {error && <Alert kind="error">{error}</Alert>}
      {!rows && !error && <Loading />}
      {rows && rows.length === 0 && <Empty>{hint || "Nothing is assigned to you right now."}</Empty>}
      {rows && rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Request</th>
                <th scope="col">Status</th>
                <th scope="col">Stage</th>
                <th scope="col">Issue</th>
                <th scope="col">Updated</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((request) => (
                <tr key={request.id}>
                  <td>
                    <Link to={`/requests/${request.id}`}>{request.title}</Link>
                    <div className="muted">{request.id}</div>
                  </td>
                  <td>
                    <StatusBadge status={request.status} />
                  </td>
                  <td>{request.stage ? request.stage.toUpperCase() : "—"}</td>
                  <td>
                    {request.issue_url ? (
                      <a href={request.issue_url} target="_blank" rel="noreferrer">
                        #{request.issue_number}
                      </a>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="nowrap">{formatDate(request.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function RequestsPage() {
  const { me } = useMe();
  return (
    <>
      <h1>Requests</h1>
      {isRequester(me) && <MyRequests />}
      {isReviewer(me) && <AssignedRequests />}
    </>
  );
}
