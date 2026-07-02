import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SessionSelector } from '../src/components/SessionSelector';
import { AppProvider, useAppContext } from '../src/context/AppContext';
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
        session_name: 'Practice 1',
        session_type: 'Practice',
        date_start: '2023-03-03T11:30:00',
        date_end: '2023-03-03T12:30:00',
      },
      {
        session_key: 7954,
        session_name: 'Qualifying',
        session_type: 'Qualifying',
        date_start: '2023-03-04T15:00:00',
        date_end: '2023-03-04T16:00:00',
      },
      {
        session_key: 7955,
        session_name: 'Race',
        session_type: 'Race',
        date_start: '2023-03-05T15:00:00',
        date_end: '2023-03-05T17:00:00',
      },
    ],
  },
  {
    meeting_key: 1142,
    meeting_name: 'Belgian Grand Prix',
    country_name: 'Belgium',
    location: 'Spa-Francorchamps',
    circuit_short_name: 'spa',
    year: 2023,
    date_start: '2023-07-28T00:00:00',
    sessions: [
      {
        session_key: 7980,
        session_name: 'Race',
        session_type: 'Race',
        date_start: '2023-07-30T15:00:00',
        date_end: '2023-07-30T17:00:00',
      },
    ],
  },
];

// Mock the apiFetch function
vi.mock('../src/api/client', () => ({
  apiFetch: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(
      public status: number,
      public body: string,
    ) {
      super(`API Error ${status}: ${body}`);
    }
  },
}));

import { apiFetch } from '../src/api/client';
const mockApiFetch = vi.mocked(apiFetch);

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
}

// Helper to capture selected session
let capturedSessionKey: number | null = null;
let capturedSessionName: string | null = null;

function SessionCapture() {
  const { selectedSessionKey, selectedSessionName } = useAppContext();
  capturedSessionKey = selectedSessionKey;
  capturedSessionName = selectedSessionName;
  return null;
}

function TestWrapper({ children }: { children: ReactNode }) {
  const queryClient = createTestQueryClient();
  return (
    <QueryClientProvider client={queryClient}>
      <AppProvider>
        {children}
        <SessionCapture />
      </AppProvider>
    </QueryClientProvider>
  );
}

describe('SessionSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    capturedSessionKey = null;
    capturedSessionName = null;
  });

  it('renders year picker with 2024 as default', () => {
    mockApiFetch.mockResolvedValue(mockMeetings);
    render(
      <TestWrapper>
        <SessionSelector />
      </TestWrapper>,
    );
    expect(screen.getByDisplayValue('2024')).toBeInTheDocument();
  });

  it('shows loading state while fetching', () => {
    mockApiFetch.mockReturnValue(new Promise(() => {})); // never resolves
    render(
      <TestWrapper>
        <SessionSelector />
      </TestWrapper>,
    );
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('displays meetings after successful fetch', async () => {
    mockApiFetch.mockResolvedValue(mockMeetings);
    render(
      <TestWrapper>
        <SessionSelector />
      </TestWrapper>,
    );
    await waitFor(() => {
      expect(screen.getByText('Bahrain Grand Prix')).toBeInTheDocument();
    });
    expect(screen.getByText('Belgian Grand Prix')).toBeInTheDocument();
  });

  it('shows error state when API fails', async () => {
    mockApiFetch.mockRejectedValue(new Error('Network error'));
    render(
      <TestWrapper>
        <SessionSelector />
      </TestWrapper>,
    );
    await waitFor(() => {
      expect(screen.getByText(/unable to load/i)).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('dispatches session_key when session clicked', async () => {
    const user = userEvent.setup();
    mockApiFetch.mockResolvedValue(mockMeetings);
    render(
      <TestWrapper>
        <SessionSelector />
      </TestWrapper>,
    );

    await waitFor(() => screen.getByText('Bahrain Grand Prix'));

    // Expand meeting
    await user.click(screen.getByText('Bahrain Grand Prix'));
    // Click Race session
    await user.click(screen.getByText('Race'));

    expect(capturedSessionKey).toBe(7955);
    expect(capturedSessionName).toBe('Bahrain Grand Prix — Race');
  });

  it('filters meetings by country', async () => {
    const user = userEvent.setup();
    mockApiFetch.mockResolvedValue(mockMeetings);
    render(
      <TestWrapper>
        <SessionSelector />
      </TestWrapper>,
    );

    await waitFor(() => screen.getByText('Bahrain Grand Prix'));

    const filter = screen.getByPlaceholderText(/filter/i);
    await user.type(filter, 'Belgium');

    expect(screen.queryByText('Bahrain Grand Prix')).not.toBeInTheDocument();
    expect(screen.getByText('Belgian Grand Prix')).toBeInTheDocument();
  });

  it('changes year and fetches new data', async () => {
    const user = userEvent.setup();
    mockApiFetch.mockResolvedValue(mockMeetings);
    render(
      <TestWrapper>
        <SessionSelector />
      </TestWrapper>,
    );

    await waitFor(() => screen.getByText('Bahrain Grand Prix'));

    const yearSelect = screen.getByDisplayValue('2024');
    await user.selectOptions(yearSelect, '2023');

    expect(mockApiFetch).toHaveBeenCalledWith('/api/v1/sessions?year=2023');
  });

  it('expands and collapses meeting sessions', async () => {
    const user = userEvent.setup();
    mockApiFetch.mockResolvedValue(mockMeetings);
    render(
      <TestWrapper>
        <SessionSelector />
      </TestWrapper>,
    );

    await waitFor(() => screen.getByText('Bahrain Grand Prix'));

    // Initially sessions are not shown
    expect(screen.queryByText('Race')).not.toBeInTheDocument();

    // Expand
    await user.click(screen.getByText('Bahrain Grand Prix'));
    expect(screen.getByText('Race')).toBeInTheDocument();
    expect(screen.getByText('Practice 1')).toBeInTheDocument();

    // Collapse
    await user.click(screen.getByText('Bahrain Grand Prix'));
    expect(screen.queryByText('Race')).not.toBeInTheDocument();
  });

  it('retry button refetches data', async () => {
    const user = userEvent.setup();
    mockApiFetch.mockRejectedValueOnce(new Error('Network error'));
    render(
      <TestWrapper>
        <SessionSelector />
      </TestWrapper>,
    );

    await waitFor(() => screen.getByText(/unable to load/i));

    mockApiFetch.mockResolvedValueOnce(mockMeetings);
    await user.click(screen.getByRole('button', { name: /retry/i }));

    await waitFor(() => {
      expect(screen.getByText('Bahrain Grand Prix')).toBeInTheDocument();
    });
  });
});
