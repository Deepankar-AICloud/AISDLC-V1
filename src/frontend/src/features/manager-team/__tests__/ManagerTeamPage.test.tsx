import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import ManagerTeamPage from '../ManagerTeamPage';
import { api } from '../../../api';

vi.mock('../../../api', () => ({
  api: {
    teamRequests: vi.fn()
  }
}));

const mockedApi = vi.mocked(api, true);

describe('ManagerTeamPage', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("lists requests within the manager's team scope", async () => {
    mockedApi.teamRequests.mockResolvedValue({
      items: [
        {
          id: 'r1', kind: 'Access', requestTypeId: 't1', requestTypeName: 'VPN Access', title: 'Need VPN',
          description: 'd', status: 'UnderReview', requesterId: 'employee-1', createdAt: '2026-01-01T00:00:00Z'
        }
      ],
      page: 1,
      pageSize: 50,
      totalCount: 1
    });

    render(<ManagerTeamPage />);

    await waitFor(() => expect(screen.getByText('Need VPN')).toBeInTheDocument());
    expect(screen.getByText('employee-1')).toBeInTheDocument();
    expect(mockedApi.teamRequests).toHaveBeenCalled();
  });

  it('shows an empty-state message when the team has no requests', async () => {
    mockedApi.teamRequests.mockResolvedValue({ items: [], page: 1, pageSize: 50, totalCount: 0 });

    render(<ManagerTeamPage />);

    await waitFor(() => expect(screen.getByText('No team requests.')).toBeInTheDocument());
  });

  it('surfaces an API error (e.g. unauthorized/forbidden) instead of silently showing no data', async () => {
    mockedApi.teamRequests.mockRejectedValue(new Error('403 Forbidden'));

    render(<ManagerTeamPage />);

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('403 Forbidden'));
  });

  it('paginates beyond the first 50 results instead of silently truncating', async () => {
    const page1Items = Array.from({ length: 50 }, (_, i) => ({
      id: `r${i}`, kind: 'Access' as const, requestTypeId: 't1', requestTypeName: 'VPN Access', title: `Req ${i}`,
      description: 'd', status: 'Submitted' as const, requesterId: 'employee-1', createdAt: '2026-01-01T00:00:00Z'
    }));
    mockedApi.teamRequests.mockResolvedValueOnce({ items: page1Items, page: 1, pageSize: 50, totalCount: 55 });

    render(<ManagerTeamPage />);

    await waitFor(() => expect(screen.getByText('Req 0')).toBeInTheDocument());
    expect(mockedApi.teamRequests).toHaveBeenCalledWith(1, 50);
    expect(screen.getByText(/Page 1 of 2/)).toBeInTheDocument();

    const page2Items = [
      {
        id: 'r50', kind: 'Access' as const, requestTypeId: 't1', requestTypeName: 'VPN Access', title: 'Req 50',
        description: 'd', status: 'Submitted' as const, requesterId: 'employee-1', createdAt: '2026-01-01T00:00:00Z'
      }
    ];
    mockedApi.teamRequests.mockResolvedValueOnce({ items: page2Items, page: 2, pageSize: 50, totalCount: 55 });

    fireEvent.click(screen.getByRole('button', { name: 'Next' }));

    await waitFor(() => expect(screen.getByText('Req 50')).toBeInTheDocument());
    expect(mockedApi.teamRequests).toHaveBeenCalledWith(2, 50);
    expect(screen.queryByText('Req 0')).not.toBeInTheDocument();
  });
});
