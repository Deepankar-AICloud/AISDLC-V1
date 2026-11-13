import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorText } from "../api";
import { isRequester, isReviewer, useMe } from "../App";
import { Alert, Empty, Loading, StatusBadge, formatDate } from "../components/ui";
import type { RequestSummary } from "../types";

function RequestTable({ rows }: { rows: RequestSummary[] }) {
  return (
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
          {rows.map((r) => (
            <tr key={r.id}>
              <td>
                <Link to={`/requests/${r.id}`}>{r.title}</Link>
                <div className="muted">{r.id}</div>
              </td>
              <td>
                <StatusBadge status={r.status} />
              </td>
              <td>{r.stage ? r.stage.toUpperCase() : "—"}</td>
              <td>
                {r.issue_url ? (
                  <a href={r.issue_url} target="_blank" rel="noreferrer">
                    #{r.issue_number}
                  </a>
                ) : (
                  "—"
                )}
              </td>
              <td className="nowrap">{formatDate(r.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Section({ scope, title }: { scope: "mine" | "assigned"; title: string }) {
  const [rows, setRows] = useState<RequestSummary[] | null>(null);
  const [hint, setHint] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    api<{ requests: RequestSummary[]; hint?: string }>(`/api/requests?scope=${scope}`)
      .then((r) => {
        setRows(r.requests);
        setHint(r.hint ?? "");
      })
      .catch((e) => setError(errorText(e)));
  }, [scope]);
  return (
    <section aria-labelledby={`h-${scope}`}>
      <h2 id={`h-${scope}`}>{title}</h2>
      {error && <Alert kind="error">{error}</Alert>}
      {!rows && !error && <Loading />}
      {rows && rows.length === 0 && (
        <Empty>
          {hint ||
            (scope === "mine" ? (
              <>
                No requests yet. <Link to="/new">Submit a requirement</Link>.
              </>
            ) : (
              "Nothing is assigned to you right now."
            ))}
        </Empty>
      )}
      {rows && rows.length > 0 && <RequestTable rows={rows} />}
    </section>
  );
}

export function RequestsPage() {
  const { me } = useMe();
  return (
    <>
      <h1>Requests</h1>
      {isRequester(me) && <Section scope="mine" title="My requests" />}
      {isReviewer(me) && <Section scope="assigned" title="Assigned to me for review" />}
    </>
  );
}
