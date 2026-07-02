import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppProvider } from '../src/context/AppContext';
import { CircuitCanvas } from '../src/components/CircuitCanvas';

// Mock pixi.js
vi.mock('pixi.js', () => ({
  Application: vi.fn().mockImplementation(() => ({
    init: vi.fn().mockResolvedValue(undefined),
    canvas: document.createElement('canvas'),
    stage: { removeChildren: vi.fn(), addChild: vi.fn() },
    screen: { width: 800, height: 600 },
    destroy: vi.fn(),
  })),
  Graphics: vi.fn().mockImplementation(() => ({
    setStrokeStyle: vi.fn().mockReturnThis(),
    moveTo: vi.fn().mockReturnThis(),
    lineTo: vi.fn().mockReturnThis(),
    stroke: vi.fn().mockReturnThis(),
    circle: vi.fn().mockReturnThis(),
    fill: vi.fn().mockReturnThis(),
    beginPath: vi.fn().mockReturnThis(),
  })),
}));

// Mock useCircuitGeometry
const mockUseCircuitGeometry = vi.fn();
vi.mock('../src/hooks/useCircuitGeometry', () => ({
  useCircuitGeometry: (...args: unknown[]) => mockUseCircuitGeometry(...args),
}));

function TestWrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={queryClient}>
      <AppProvider>{children}</AppProvider>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('CircuitCanvas', () => {
  it('shows loading state when fetching', () => {
    mockUseCircuitGeometry.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    });

    render(
      <TestWrapper>
        <CircuitCanvas />
      </TestWrapper>,
    );
    expect(screen.getByText(/loading circuit/i)).toBeInTheDocument();
    expect(document.querySelector('.circuit-canvas')).toBeInTheDocument();
  });

  it('shows error state on fetch failure', () => {
    mockUseCircuitGeometry.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Network error'),
    });

    render(
      <TestWrapper>
        <CircuitCanvas />
      </TestWrapper>,
    );
    expect(screen.getByText(/failed to load circuit/i)).toBeInTheDocument();
  });

  it('renders canvas container when data is available', () => {
    mockUseCircuitGeometry.mockReturnValue({
      data: {
        session_key: 9472,
        total_points: 100,
        total_length: 5000,
        bounds: { min_x: 0, max_x: 1000, min_y: 0, max_y: 500 },
        points: [{ x: 0, y: 0, cumulative_dist: 0 }],
        segments: [],
        source_driver: 1,
        source_lap: 1,
      },
      isLoading: false,
      error: null,
    });

    render(
      <TestWrapper>
        <CircuitCanvas />
      </TestWrapper>,
    );
    expect(document.querySelector('.circuit-canvas')).toBeInTheDocument();
    expect(screen.queryByText(/loading circuit/i)).not.toBeInTheDocument();
  });
});
