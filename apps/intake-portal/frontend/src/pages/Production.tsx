import { useCallback, useEffect, useState } from "react";
import { api, errorText } from "../api";
import { isReviewer, useMe } from "../App";
import { Alert, Empty, Loading, formatDate } from "../components/ui";
import type { ProductionListing, ProductionRun } from "../types";

function RunCard({ run, word, onDone }: { run: ProductionRun; word: string; onDone: () => void }) {
  const [typed, setTyped] = useState("");
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  async function approve() {
    setBusy(true);
    setMsg(null);
    try {
      const r = await api<{ github_login: string }>(`/api/production/${run.run_id}/approve`, {
        json: { confirmation: typed, comment },
      });
      setMsg({ kind: "ok", text: `Production deployment approved on GitHub as ${r.github_login}.` });
      onDone();
    } catch (e) {
      setMsg({ kind: "error", text: errorText(e) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card" aria-labelledby={`run-${run.run_id}`}>
      <h2 id={`run-${run.run_id}`}>
        Release run{" "}
        <a href={run.url} target="_blank" rel="noreferrer">
          #{run.run_id}
        </a>
      </h2>
      <p className="muted">
        Commit <code>{run.head_sha.slice(0, 12)}</code> · waiting since {formatDate(run.created_at)}
      </p>
      <h3>Release evidence</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Check</th>
              <th scope="col">Result</th>
            </tr>
          </thead>
          <tbody>
            {run.evidence.map((e) => (
              <tr key={e.name}>
                <td>
                  {e.name} {e.note && <span className="muted">({e.note})</span>}
                </td>
                <td>
                  <span className={`badge ${e.conclusion === "success" ? "ok" : e.conclusion ? "danger" : "warn"}`}>
                    {e.conclusion ?? e.status}
                  </span>{" "}
                  {e.url && (
                    <a href={e.url} target="_blank" rel="noreferrer">
                      details
                    </a>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      {run.can_approve ? (
        <>
          <div className="field">
            <label htmlFor={`confirm-${run.run_id}`}>Type “{word}” to approve the production release</label>
            <input
              id={`confirm-${run.run_id}`}
              autoComplete="off"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor={`comment-${run.run_id}`}>Comment (optional)</label>
            <input id={`comment-${run.run_id}`} value={comment} onChange={(e) => setComment(e.target.value)} />
          </div>
          <button type="button" className="danger" disabled={typed !== word || busy} onClick={approve}>
            {busy ? "Approving…" : "Approve production release"}
          </button>
        </>
      ) : (
        <Alert kind="info">{run.reason}</Alert>
      )}
    </section>
  );
}

export function ProductionPage() {
  const { me } = useMe();
  const [data, setData] = useState<ProductionListing | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api<ProductionListing>("/api/production")
      .then(setData)
      .catch((e) => setError(errorText(e)));
  }, []);

  useEffect(() => {
    if (isReviewer(me)) load();
  }, [load, me]);

  if (!isReviewer(me)) return <Alert kind="info">Production approvals need the Reviewer role.</Alert>;
  if (error) return <Alert kind="error">{error}</Alert>;
  if (!data) return <Loading />;

  return (
    <>
      <h1>Production releases</h1>
      <p>
        Only required reviewers of the GitHub <code>production</code> environment can approve. The approval is made with
        your own GitHub account; GitHub decides who may approve.
      </p>
      {data.environment.problem ? (
        <Alert kind="error" title="Production is not protected">
          {data.environment.problem}
        </Alert>
      ) : (
        <p className="muted">Required reviewers: {data.environment.reviewers.join(", ")}</p>
      )}
      {!me.github.connected && (
        <Alert kind="info">
          <a href="/auth/github/connect">Connect GitHub</a> to see whether you can approve.
        </Alert>
      )}
      {data.runs.length === 0 ? (
        <Empty>No production deployment is waiting for approval.</Empty>
      ) : (
        data.runs.map((r) => <RunCard key={r.run_id} run={r} word={data.confirmation_word} onDone={load} />)
      )}
    </>
  );
}
