import React, { useEffect, useState } from 'react';
import { api, AccessRequest, RequestCategory } from './api';

const CATEGORIES: RequestCategory[] = [
  'GitHubAccess', 'AzureAccess', 'VpnAccess', 'ApplicationAccess',
  'DatabaseAccess', 'ProductionAccess', 'SoftwareInstallation',
  'LaptopRequest', 'HardwareRequest', 'PasswordSupport', 'GeneralSupport'
];

export default function App(): React.ReactElement {
  const [requests, setRequests] = useState<AccessRequest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    title: '',
    description: '',
    category: 'GitHubAccess' as RequestCategory
  });

  async function refresh(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      setRequests(await api.list());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function submit(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    setError(null);
    try {
      await api.create(form);
      setForm({ title: '', description: '', category: 'GitHubAccess' });
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <main style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 920, margin: '2rem auto', padding: '0 1rem' }}>
      <h1>SmartServe</h1>
      <p>Enterprise IT Service &amp; Access Request Portal</p>

      {error && (
        <div role="alert" style={{ background: '#fde2e1', padding: '0.75rem', borderRadius: 6, marginBottom: 12 }}>
          {error}
        </div>
      )}

      <section style={{ border: '1px solid #ddd', borderRadius: 8, padding: 16, marginBottom: 24 }}>
        <h2>New request</h2>
        <form onSubmit={submit}>
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
          <div style={{ marginBottom: 8 }}>
            <label>
              Category{' '}
              <select
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value as RequestCategory })}
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
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
              <th style={th}>Category</th>
              <th style={th}>Status</th>
              <th style={th}>Security review</th>
              <th style={th}>Created</th>
            </tr>
          </thead>
          <tbody>
            {requests.map((r) => (
              <tr key={r.id}>
                <td style={td}>{r.title}</td>
                <td style={td}>{r.category}</td>
                <td style={td}>{r.status}</td>
                <td style={td}>{r.requiresSecurityReview ? 'Yes' : 'No'}</td>
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
