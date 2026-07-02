import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useSessions } from '../src/hooks/useSessions';
import { ReactNode } from 'react';

const mockMeetings = [
  {
    meeting_key: 1141,
    meeting_name: 'Bahrain Grand Prix',
    country_name: 'Bahrain',
    location: 'Sakhir',
    circuit_short_name: 'bahrain',
    year: 2023,
    date_start: '2023-03-03T00:00:00',
    sessions: [
      {
        session_key: 7953,
        session_name: 'Race',
        session_type: 'Race',
        date_start: '2023-03-05T15:00:00',
        date_end: '2023-03-05T17:00:00',
      },
    ],
  },
];

vi.mock('../src/api/client', () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from '../src/api/client';
const mockApiFetch = vi.mocked(apiFetch);

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useSessions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('does not fetch when year is null', () => {
    renderHook(() => useSessions(null), { wrapper: createWrapper() });
    expect(mockApiFetch).not.toHaveBeenCalled();
  });

  it('fetches sessions for a given year', async () => {
    mockApiFetch.mockResolvedValue(mockMeetings);
    const { result } = renderHook(() => useSessions(2023), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockApiFetch).toHaveBeenCalledWith('/api/v1/sessions?year=2023');
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data![0].meeting_name).toBe('Bahrain Grand Prix');
  });

  it('validates response with zod schema', async () => {
    // Invalid data — missing required field
    mockApiFetch.mockResolvedValue([{ meeting_key: 1 }]);
    const { result } = renderHook(() => useSessions(2023), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it('returns error on fetch failure', async () => {
    mockApiFetch.mockRejectedValue(new Error('Server Error'));
    const { result } = renderHook(() => useSessions(2023), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(Error);
  });
});
