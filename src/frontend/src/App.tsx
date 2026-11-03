import React, { useEffect, useState } from 'react';
import { api, PortalRequest, RequestKind, RequestType } from './api';
import AdminRequestTypesPage from './features/admin-request-types/AdminRequestTypesPage';

// (proposed) tab navigation: the PRD/Epics don't specify a nav structure, so this is a minimal wiring choice.
type Tab = 'requests' | 'admin-request-types';

export default function App(): React.ReactElement {
  const [tab, setTab] = useState<Tab>('requests');
  const [requests, setRequests] = useState<PortalRequest[]>([]);
  const [requestTypes, setRequestTypes] = useState<RequestType[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({ kind: 'Access' as RequestKind, requestTypeId: '', title: '', description: '' });

  async function refresh(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const [reqs, types] = await Promise.all([api.list(), api.requestTypes.list()]);
      setRequests(reqs);
      setRequestTypes(types);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  if (tab === 'admin-request-types') {
    return (
      <div>
        <nav style={{ maxWidth: 920, margin: '1rem auto', padding: '0 1rem' }}>
          <button type="button" onClick={() => setTab('requests')}>&larr; Back to requests</button>
        </nav>
        <AdminRequestTypesPage />
      </div>
    );
  }

  const typesForKind = requestTypes.filter((t) => t.kind === form.kind && t.isActive);

  async function submit(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    setError(null);
    try {
      await api.create(form);
      setForm({ ...form, title: '', description: '' });
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <main style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 920, margin: '2rem auto', padding: '0 1rem' }}>
      <h1>SmartServe</h1>
      <p>Enterprise IT Service &amp; Access Request Portal</p>
      <nav style={{ marginBottom: 16 }}>
        <button type="button" onClick={() => setTab('admin-request-types')}>Manage request types (admin)</button>
      </nav>

      {error && (
        <div role="alert" style={{ background: '#fde2e1', padding: '0.75rem', borderRadius: 6, marginBottom: 12 }}>
          {error}
        </div>
      )}

      <section style={{ border: '1px solid #ddd', borderRadius: 8, padding: 16, marginBottom: 24 }}>
        <h2>New request</h2>
        {/* (proposed) Submission form fields and labels: not specified by ARCH-23/TASK-23. */}
        <form onSubmit={submit}>
          <div style={{ marginBottom: 8 }}>
            <label>
              Kind{' '}
              <select
                value={form.kind}
                onChange={(e) => setForm({ ...form, kind: e.target.value as RequestKind, requestTypeId: '' })}
              >
                <option value="Access">Access</option>
                <option value="Service">Service</option>
              </select>
            </label>
          </div>
          <div style={{ marginBottom: 8 }}>
            <label>
              Request type{' '}
              <select
                required
                value={form.requestTypeId}
                onChange={(e) => setForm({ ...form, requestTypeId: e.target.value })}
              >
                <option value="" disabled>Select a type…</option>
                {typesForKind.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </label>
          </div>
          <div style={{ marginBottom: 8 }}>
            <label>
              Title<br />
              <input
                required
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                style={{ width: '100%' }}
              />
            </label>
          </div>
          <div style={{ marginBottom: 8 }}>
            <label>
              Description<br />
              <textarea
                required
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                style={{ width: '100%' }}
                rows={3}
              />
            </label>
          </div>
          <button type="submit">Submit request</button>
        </form>
      </section>

      <section>
        <h2>My requests {loading && <small>(loading…)</small>}</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={th}>Title</th>
              <th style={th}>Kind</th>
              <th style={th}>Type</th>
              <th style={th}>Status</th>
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
                <td style={td}>{new Date(r.createdAt).toLocaleString()}</td>
              </tr>
            ))}
            {requests.length === 0 && !loading && (
              <tr><td style={td} colSpan={5}>No requests yet.</td></tr>
            )}
          </tbody>
        </table>
      </section>
    </main>
  );
}

const th: React.CSSProperties = { textAlign: 'left', borderBottom: '2px solid #ccc', padding: '6px 8px' };
const td: React.CSSProperties = { borderBottom: '1px solid #eee', padding: '6px 8px' };
