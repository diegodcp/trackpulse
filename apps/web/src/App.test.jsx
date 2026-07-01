import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { delay, http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { App } from './App';
import { server, trackSnapshotFixture } from './test/server';

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

describe('TP-BH-0012 Bahrain circuit map', () => {
  it('renders circuit map with expected segment count', () => {
    render(<App />);

    const circuitMapSvg = screen.getByRole('img', { name: /Circuit map with 16 segments/ });
    expect(circuitMapSvg).toBeInTheDocument();
  });

  it('shows stylized precision disclaimer', () => {
    render(<App />);

    expect(
      screen.getByText('Stylized Bahrain circuit. Approximate geometry only; no racing-line precision is claimed.')
    ).toBeInTheDocument();
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

  it('shows traffic truth label as derived when traffic layer is active', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', { name: 'Traffic' }));

    expect(screen.getByText(/Traffic density overlay is/i)).toBeInTheDocument();
    expect(within(screen.getByTestId('traffic-derived-note')).getByText('Derived')).toBeInTheDocument();
  });
});

describe('TP-BH-0013 Track snapshot connection', () => {
  it('renders measured weather values from track snapshot fixture', async () => {
    render(<App />);

    expect(
      await screen.findAllByText(`${trackSnapshotFixture.snapshot.weather.track_temperature_c.toFixed(1)} C`)
    ).toHaveLength(2);
    expect(screen.getByText(`${trackSnapshotFixture.snapshot.weather.air_temperature_c.toFixed(1)} C`)).toBeInTheDocument();
    expect(
      screen.getByText(
        `${trackSnapshotFixture.snapshot.weather.wind_speed_ms.toFixed(1)} m/s @ ${trackSnapshotFixture.snapshot.weather.wind_direction_deg} deg`
      )
    ).toBeInTheDocument();
    expect(screen.getByText('No rain detected')).toBeInTheDocument();
    const statusSection = screen.getByRole('region', { name: 'Session status' });
    expect(within(statusSection).getByText('measured')).toBeInTheDocument();
    expect(within(statusSection).getByText('connected')).toBeInTheDocument();
    expect(within(statusSection).getByText('paused')).toBeInTheDocument();
  });

  it('shows loading state while waiting for track snapshot', async () => {
    server.use(
      http.get('/api/v1/track-state/latest', async () => {
        await delay(200);
        return HttpResponse.json(trackSnapshotFixture);
      })
    );

    render(<App />);

    expect(await screen.findByText('Loading measured weather...')).toBeInTheDocument();
  });

  it('shows safe error state when track snapshot request fails', async () => {
    server.use(
      http.get('/api/v1/track-state/latest', () => HttpResponse.json({ detail: 'boom' }, { status: 500 }))
    );

    render(<App />);

    expect(
      await screen.findByText('Track snapshot unavailable. Please try again shortly.')
    ).toBeInTheDocument();
  });

  it('shows empty state when track snapshot payload is missing snapshot', async () => {
    server.use(http.get('/api/v1/track-state/latest', () => HttpResponse.json({})));

    render(<App />);

    expect(await screen.findByText('No track snapshot available.')).toBeInTheDocument();
  });

  it('app-level flow shows global track temperature badge', async () => {
    render(<App />);

    expect(await screen.findAllByText('43.2 C')).toHaveLength(2);
    expect(screen.getByText('Track Temp Badge')).toBeInTheDocument();
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
    expect(screen.getByText('Car markers use measured replay locations but are displayed as approximate positions.')).toBeInTheDocument();
    expect(await screen.findByTestId('replay-car-marker')).toBeInTheDocument();
  });
});
