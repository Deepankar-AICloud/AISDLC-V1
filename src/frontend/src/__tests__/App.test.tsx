import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import App from '../App';
import { api } from '../api';

vi.mock('../api', () => ({
  api: {
    list: vi.fn().mockResolvedValue([]),
    requestTypes: {
      list: vi.fn().mockResolvedValue([])
    },
    create: vi.fn()
  }
}));

const mockedApi = vi.mocked(api, true);

describe('App', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('navigates to the admin request-types page and back', async () => {
    render(<App />);
    await waitFor(() => expect(mockedApi.list).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /manage request types/i }));
    expect(await screen.findByText('Request type administration')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /back to requests/i }));
    expect(await screen.findByText('SmartServe')).toBeInTheDocument();
  });
});
