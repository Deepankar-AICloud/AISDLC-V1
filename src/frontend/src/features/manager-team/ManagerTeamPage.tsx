import React, { useEffect, useState } from 'react';
import { api, PortalRequest } from '../../api';

const PAGE_SIZE = 50;

// (proposed) Manager team view: lists requests within the caller's currently-authorized team scope (TASK-010).
// Server resolves scope fresh on every call (never from a stored field) and enforces the "CanViewTeamRequests"
// policy; this page renders whatever the API returns and paginates beyond the first page so large teams are fully visible.
export default function ManagerTeamPage(): React.ReactElement {
  const [requests, setRequests] = useState<PortalRequest[]>([]);
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function refresh(targetPage: number): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const result = await api.teamRequests(targetPage, PAGE_SIZE);
      setRequests(result.items);
      setTotalCount(result.totalCount);
      setPage(targetPage);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  return (
    <section style={{ border: '1px solid #ddd', borderRadius: 8, padding: 16, marginBottom: 24 }}>
      <h2>My team&apos;s requests {loading && <small>(loading…)</small>}</h2>

      {error && (
        <div role="alert" style={{ background: '#fde2e1', padding: '0.75rem', borderRadius: 6, marginBottom: 12 }}>
          {error}
        </div>
      )}

      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={th}>Title</th>
            <th style={th}>Kind</th>
            <th style={th}>Type</th>
            <th style={th}>Status</th>
            <th style={th}>Requester</th>
            <th style={th}>Created</th>
          </tr>
        </thead>
        <tbody>
          {requests.map((r) => (
            <tr key={r.id}>
              <td style={td}>{r.title}</td>
              <td style={td}>{r.kind}</td>
              <td style={td}>{r.requestTypeName}</td>
              <td style={td}>{r.status}</td>
              <td style={td}>{r.requesterId}</td>
              <td style={td}>{new Date(r.createdAt).toLocaleString()}</td>
            </tr>
          ))}
          {requests.length === 0 && !loading && (
            <tr><td style={td} colSpan={6}>No team requests.</td></tr>
          )}
        </tbody>
      </table>

      {totalCount > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 12 }}>
          <button type="button" disabled={loading || page <= 1} onClick={() => void refresh(page - 1)}>
            Previous
          </button>
          <span>
            Page {page} of {totalPages} ({totalCount} total)
          </span>
          <button type="button" disabled={loading || page >= totalPages} onClick={() => void refresh(page + 1)}>
            Next
          </button>
        </div>
      )}
    </section>
  );
}

const th: React.CSSProperties = { textAlign: 'left', borderBottom: '2px solid #ccc', padding: '6px 8px' };
const td: React.CSSProperties = { borderBottom: '1px solid #eee', padding: '6px 8px' };
