import React, { useEffect, useState } from 'react';
import { api, RequestKind, RequestType } from '../../api';

// (proposed) App-admin page: create, edit, deactivate request types (confirmed); no reactivation action/endpoint.
export default function AdminRequestTypesPage(): React.ReactElement {
  const [types, setTypes] = useState<RequestType[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({ kind: 'Access' as RequestKind, name: '', description: '' });

  async function refresh(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      setTypes(await api.requestTypes.list());
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
      if (editingId) {
        await api.requestTypes.update(editingId, { name: form.name, description: form.description });
      } else {
        await api.requestTypes.create(form);
      }
      setForm({ kind: 'Access', name: '', description: '' });
      setEditingId(null);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function startEdit(t: RequestType): void {
    setEditingId(t.id);
    setForm({ kind: t.kind, name: t.name, description: t.description ?? '' });
  }

  async function deactivate(id: string): Promise<void> {
    setError(null);
    try {
      await api.requestTypes.deactivate(id);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <main style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 920, margin: '2rem auto', padding: '0 1rem' }}>
      <h1>Request type administration</h1>

      {error && <div role="alert">{error}</div>}

      <form onSubmit={submit} aria-label={editingId ? 'Edit request type' : 'Create request type'}>
        <div>
          <label>
            Kind{' '}
            <select
              value={form.kind}
              disabled={editingId !== null}
              onChange={(e) => setForm({ ...form, kind: e.target.value as RequestKind })}
            >
              <option value="Access">Access</option>
              <option value="Service">Service</option>
            </select>
          </label>
        </div>
        <div>
          <label>
            Name{' '}
            <input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </label>
        </div>
        <div>
          <label>
            Description{' '}
            <input
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </label>
        </div>
        <button type="submit">{editingId ? 'Save changes' : 'Create request type'}</button>
        {editingId && (
          <button type="button" onClick={() => { setEditingId(null); setForm({ kind: 'Access', name: '', description: '' }); }}>
            Cancel
          </button>
        )}
      </form>

      <h2>Existing types {loading && <small>(loading…)</small>}</h2>
      <table>
        <thead>
          <tr>
            <th>Kind</th>
            <th>Name</th>
            <th>Active</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {types.map((t) => (
            <tr key={t.id}>
              <td>{t.kind}</td>
              <td>{t.name}</td>
              <td>{t.isActive ? 'Yes' : 'No'}</td>
              <td>
                <button type="button" onClick={() => startEdit(t)}>Edit</button>
                {t.isActive && (
                  <button type="button" onClick={() => void deactivate(t.id)}>Deactivate</button>
                )}
              </td>
            </tr>
          ))}
          {types.length === 0 && !loading && (
            <tr><td colSpan={4}>No request types yet.</td></tr>
          )}
        </tbody>
      </table>
    </main>
  );
}
