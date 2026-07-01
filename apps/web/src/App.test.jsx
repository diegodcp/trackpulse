import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { App } from './App';
import { server, weatherFixture } from './test/server';

describe('TP-FE-01 UI shell', () => {
  it('renders app shell elements', () => {
    render(<App />);

    expect(screen.getByRole('heading', { name: 'TrackPulse' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Session Status' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Live Insights' })).toBeInTheDocument();
  });

  it('changes the active layer', async () => {
    const user = userEvent.setup();
    render(<App />);

    const trackTempButton = screen.getByRole('button', { name: 'Track Temp' });
    const gripButton = screen.getByRole('button', { name: 'Grip' });

    expect(trackTempButton).toHaveAttribute('aria-pressed', 'true');
    expect(gripButton).toHaveAttribute('aria-pressed', 'false');

    await user.click(gripButton);

    expect(trackTempButton).toHaveAttribute('aria-pressed', 'false');
    expect(gripButton).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText('Active Layer: Grip')).toBeInTheDocument();
  });

  it('shows confidence and truth label in an insight card', () => {
    render(<App />);

    expect(screen.getByText('Confidence: 84%')).toBeInTheDocument();
    expect(screen.getByText('Inferred')).toBeInTheDocument();
  });
});

describe('TP-FE-02 Synthetic circuit map', () => {
  it('renders circuit map with expected segment count', () => {
    render(<App />);

    const circuitMapSvg = screen.getByRole('img', { name: /Circuit map with 12 segments/ });
    expect(circuitMapSvg).toBeInTheDocument();
  });

  it('displays tooltip on segment hover', async () => {
    const user = userEvent.setup();
    render(<App />);

    const segments = screen.getAllByRole('button').filter((btn) =>
      btn.getAttribute('aria-label')?.includes('segment')
    );

    if (segments.length > 0) {
      await user.hover(segments[0]);

      // Tooltip should appear with segment information
      const tooltipElements = screen.queryAllByText(/sector|Braking|straight/i);
      expect(tooltipElements.length).toBeGreaterThan(0);
    }
  });

  it('applies layer class when active layer changes', async () => {
    const user = userEvent.setup();
    render(<App />);

    const gripButton = screen.getByRole('button', { name: 'Grip' });
    await user.click(gripButton);

    expect(screen.getByText('Active Layer: Grip')).toBeInTheDocument();

    // Segments should have the grip layer class
    const segmentElements = document.querySelectorAll('.layer-grip');
    expect(segmentElements.length).toBeGreaterThan(0);
  });

  it('toggles wind layer overlay arrows', async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(screen.queryByLabelText('Wind layer arrows (derived)')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Wind' }));

    expect(screen.getByText('Active Layer: Wind')).toBeInTheDocument();
    expect(screen.getByLabelText('Wind layer arrows (derived)')).toBeInTheDocument();
  });

  it('track map header displays active layer', () => {
    render(<App />);

    expect(screen.getByText('Active Layer: Track Temp')).toBeInTheDocument();
  });
});

describe('TP-FE-03 Weather banner connection', () => {
  it('renders measured weather values from MSW fixture', async () => {
    render(<App />);

    expect(await screen.findByText(`${weatherFixture.track_temperature.toFixed(1)} C`)).toBeInTheDocument();
    expect(screen.getByText(`${weatherFixture.air_temperature.toFixed(1)} C`)).toBeInTheDocument();
    expect(
      screen.getByText(`${weatherFixture.wind_speed.toFixed(1)} m/s @ ${weatherFixture.wind_direction} deg`)
    ).toBeInTheDocument();
    expect(screen.getByText('No rain detected')).toBeInTheDocument();
    const statusSection = screen.getByRole('region', { name: 'Session status' });
    expect(within(statusSection).getByText('Measured')).toBeInTheDocument();
  });

  it('shows safe error state when payload is invalid', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ track_temperature: 'not-a-number' })
    });

    render(<App />);

    expect(
      await screen.findByText('Measured weather unavailable. Please try again shortly.')
    ).toBeInTheDocument();

    fetchSpy.mockRestore();
  });

  it('app-level flow shows track temperature', async () => {
    render(<App />);

    expect(await screen.findByText('43.2 C')).toBeInTheDocument();
  });

  it('shows fixture replay controls and map marker', async () => {
    render(<App />);

    expect(await screen.findByLabelText('Fixture replay controls')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Play' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '1x' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '5x' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '10x' })).toBeInTheDocument();
    expect(screen.getByTestId('replay-scrubber')).toBeInTheDocument();
    expect(screen.getByTestId('replay-time')).toBeInTheDocument();
    expect(screen.getByTestId('replay-car-marker')).toBeInTheDocument();
  });
});
