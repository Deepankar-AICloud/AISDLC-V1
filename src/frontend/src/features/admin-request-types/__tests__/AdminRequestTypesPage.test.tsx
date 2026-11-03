import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import AdminRequestTypesPage from '../AdminRequestTypesPage';
import { api } from '../../../api';

vi.mock('../../../api', () => ({
  api: {
    requestTypes: {
      list: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      deactivate: vi.fn()
    }
  }
}));

const mockedApi = vi.mocked(api, true);

describe('AdminRequestTypesPage', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('lists existing request types and lets an admin create a new one', async () => {
    mockedApi.requestTypes.list
      .mockResolvedValueOnce([
        { id: 't1', kind: 'Access', name: 'VPN Access', description: null, isActive: true, createdAt: '2026-01-01T00:00:00Z' }
      ])
      .mockResolvedValueOnce([
        { id: 't1', kind: 'Access', name: 'VPN Access', description: null, isActive: true, createdAt: '2026-01-01T00:00:00Z' },
        { id: 't2', kind: 'Service', name: 'Monitor Request', description: 'Extra monitor', isActive: true, createdAt: '2026-01-02T00:00:00Z' }
      ]);
    mockedApi.requestTypes.create.mockResolvedValue({
      id: 't2', kind: 'Service', name: 'Monitor Request', description: 'Extra monitor', isActive: true, createdAt: '2026-01-02T00:00:00Z'
    });

    render(<AdminRequestTypesPage />);

    await waitFor(() => expect(screen.getByText('VPN Access')).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText('Kind'), { target: { value: 'Service' } });
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Monitor Request' } });
    fireEvent.change(screen.getByLabelText('Description'), { target: { value: 'Extra monitor' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create request type' }));

    await waitFor(() => expect(mockedApi.requestTypes.create).toHaveBeenCalledWith({
      kind: 'Service',
      name: 'Monitor Request',
      description: 'Extra monitor'
    }));
    await waitFor(() => expect(screen.getByText('Monitor Request')).toBeInTheDocument());
  });

  it('deactivates a request type and does not offer reactivation', async () => {
    mockedApi.requestTypes.list
      .mockResolvedValueOnce([
        { id: 't1', kind: 'Access', name: 'VPN Access', description: null, isActive: true, createdAt: '2026-01-01T00:00:00Z' }
      ])
      .mockResolvedValueOnce([
        { id: 't1', kind: 'Access', name: 'VPN Access', description: null, isActive: false, createdAt: '2026-01-01T00:00:00Z', deactivatedAt: '2026-01-03T00:00:00Z' }
      ]);
    mockedApi.requestTypes.deactivate.mockResolvedValue({
      id: 't1', kind: 'Access', name: 'VPN Access', description: null, isActive: false, createdAt: '2026-01-01T00:00:00Z'
    });

    render(<AdminRequestTypesPage />);

    await waitFor(() => expect(screen.getByText('VPN Access')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Deactivate' }));

    await waitFor(() => expect(mockedApi.requestTypes.deactivate).toHaveBeenCalledWith('t1'));
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Deactivate' })).not.toBeInTheDocument());
    // No reactivation control exists anywhere on the page once a type is deactivated.
    expect(screen.queryByRole('button', { name: /reactivate/i })).not.toBeInTheDocument();
  });
});
