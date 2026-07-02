import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { delay, http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { ReplayControls } from './ReplayControls';
import { server, replayStatusFixture } from '../test/server';

describe('TP-BH-0021 ReplayControls', () => {
  it('renders fixture ID and session name', async () => {
    render(<ReplayControls fixtureId="bahrain-2023-race" sessionName="Bahrain 2023 Race" />);

    expect(screen.getByTestId('replay-fixture-info')).toHaveTextContent('bahrain-2023-race');
    expect(screen.getByTestId('replay-fixture-info')).toHaveTextContent('Bahrain 2023 Race');
  });

  it('renders fixture ID without session name when not provided', () => {
    render(<ReplayControls fixtureId="bahrain-2023-race" />);

    expect(screen.getByTestId('replay-fixture-info')).toHaveTextContent('bahrain-2023-race');
  });

  it('renders all four speed options', () => {
    render(<ReplayControls fixtureId="bahrain-2023-race" />);

    const speedGroup = screen.getByRole('group', { name: 'Replay speed' });
    expect(within(speedGroup).getByText('1x')).toBeInTheDocument();
    expect(within(speedGroup).getByText('5x')).toBeInTheDocument();
    expect(within(speedGroup).getByText('20x')).toBeInTheDocument();
    expect(within(speedGroup).getByText('100x')).toBeInTheDocument();
  });

  it('shows Resume label and disables Pause when status is paused', async () => {
    render(<ReplayControls fixtureId="bahrain-2023-race" />);

    // Default fixture status is paused
    await waitFor(() => {
      expect(screen.getByTestId('replay-status')).toHaveTextContent('paused');
    });

    expect(screen.getByTestId('replay-start-btn')).toHaveTextContent('Resume');
    expect(screen.getByTestId('replay-start-btn')).not.toBeDisabled();
    expect(screen.getByTestId('replay-pause-btn')).toBeDisabled();
    expect(screen.getByTestId('replay-stop-btn')).not.toBeDisabled();
  });

  it('shows Start label and disables Pause/Stop when status is idle', async () => {
    server.use(
      http.get('/api/v1/events/replay-status', () =>
        HttpResponse.json({ ...replayStatusFixture, status: 'idle' })
      )
    );

    render(<ReplayControls fixtureId="bahrain-2023-race" />);

    await waitFor(() => {
      expect(screen.getByTestId('replay-status')).toHaveTextContent('idle');
    });

    expect(screen.getByTestId('replay-start-btn')).toHaveTextContent('Start');
    expect(screen.getByTestId('replay-start-btn')).not.toBeDisabled();
    expect(screen.getByTestId('replay-pause-btn')).toBeDisabled();
    expect(screen.getByTestId('replay-stop-btn')).toBeDisabled();
  });

  it('disables Start and enables Pause/Stop when status is running', async () => {
    server.use(
      http.get('/api/v1/events/replay-status', () =>
        HttpResponse.json({ ...replayStatusFixture, status: 'running' })
      )
    );

    render(<ReplayControls fixtureId="bahrain-2023-race" />);

    await waitFor(() => {
      expect(screen.getByTestId('replay-status')).toHaveTextContent('running');
    });

    expect(screen.getByTestId('replay-start-btn')).toBeDisabled();
    expect(screen.getByTestId('replay-pause-btn')).not.toBeDisabled();
    expect(screen.getByTestId('replay-stop-btn')).not.toBeDisabled();
  });

  it('calls start endpoint and updates status to running', async () => {
    const user = userEvent.setup();
    let startCalled = false;

    server.use(
      http.get('/api/v1/events/replay-status', () =>
        HttpResponse.json({ ...replayStatusFixture, status: startCalled ? 'running' : 'idle' })
      ),
      http.post('/api/v1/replay/:fixtureId/start', async ({ request }) => {
        const body = await request.json();
        startCalled = true;
        return HttpResponse.json({
          ...replayStatusFixture,
          status: 'running',
          speed_multiplier: body.speed_multiplier ?? 1,
          message: 'Replay started'
        });
      })
    );

    render(<ReplayControls fixtureId="bahrain-2023-race" />);

    await waitFor(() => {
      expect(screen.getByTestId('replay-start-btn')).not.toBeDisabled();
    });

    await user.click(screen.getByTestId('replay-start-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('replay-status')).toHaveTextContent('running');
    });
  });

  it('calls pause endpoint and updates status to paused', async () => {
    const user = userEvent.setup();
    let pauseCalled = false;

    server.use(
      http.get('/api/v1/events/replay-status', () =>
        HttpResponse.json({ ...replayStatusFixture, status: pauseCalled ? 'paused' : 'running' })
      ),
      http.post('/api/v1/replay/:fixtureId/pause', () => {
        pauseCalled = true;
        return HttpResponse.json({
          ...replayStatusFixture,
          status: 'paused',
          message: 'Replay paused'
        });
      })
    );

    render(<ReplayControls fixtureId="bahrain-2023-race" />);

    await waitFor(() => {
      expect(screen.getByTestId('replay-pause-btn')).not.toBeDisabled();
    });

    await user.click(screen.getByTestId('replay-pause-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('replay-status')).toHaveTextContent('paused');
    });
  });

  it('calls stop endpoint and updates status to idle', async () => {
    const user = userEvent.setup();
    let stopCalled = false;

    server.use(
      http.get('/api/v1/events/replay-status', () =>
        HttpResponse.json({ ...replayStatusFixture, status: stopCalled ? 'idle' : 'running' })
      ),
      http.post('/api/v1/replay/:fixtureId/stop', () => {
        stopCalled = true;
        return HttpResponse.json({
          ...replayStatusFixture,
          status: 'idle',
          message: 'Replay stopped'
        });
      })
    );

    render(<ReplayControls fixtureId="bahrain-2023-race" />);

    await waitFor(() => {
      expect(screen.getByTestId('replay-stop-btn')).not.toBeDisabled();
    });

    await user.click(screen.getByTestId('replay-stop-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('replay-status')).toHaveTextContent('idle');
    });
  });

  it('displays replay time from status endpoint', async () => {
    render(<ReplayControls fixtureId="bahrain-2023-race" />);

    await waitFor(() => {
      expect(screen.getByTestId('replay-time')).not.toHaveTextContent('--');
    });

    expect(screen.getByTestId('replay-time')).toHaveTextContent('2023-03-05');
  });

  it('marks 1x speed as active by default', async () => {
    render(<ReplayControls fixtureId="bahrain-2023-race" />);

    await waitFor(() => {
      expect(screen.getByTestId('replay-speed-1x')).toHaveClass('is-active');
    });

    expect(screen.getByTestId('replay-speed-5x')).not.toHaveClass('is-active');
    expect(screen.getByTestId('replay-speed-20x')).not.toHaveClass('is-active');
    expect(screen.getByTestId('replay-speed-100x')).not.toHaveClass('is-active');
  });

  it('shows error alert when start request fails', async () => {
    const user = userEvent.setup();

    server.use(
      http.get('/api/v1/events/replay-status', () =>
        HttpResponse.json({ ...replayStatusFixture, status: 'idle' })
      ),
      http.post('/api/v1/replay/:fixtureId/start', () =>
        HttpResponse.json({ error: 'Server error' }, { status: 500 })
      )
    );

    render(<ReplayControls fixtureId="bahrain-2023-race" />);

    await waitFor(() => {
      expect(screen.getByTestId('replay-start-btn')).not.toBeDisabled();
    });

    await user.click(screen.getByTestId('replay-start-btn'));

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Failed to start replay');
  });

  it('shows error alert when pause request fails', async () => {
    const user = userEvent.setup();

    server.use(
      http.get('/api/v1/events/replay-status', () =>
        HttpResponse.json({ ...replayStatusFixture, status: 'running' })
      ),
      http.post('/api/v1/replay/:fixtureId/pause', () =>
        HttpResponse.json({ error: 'Server error' }, { status: 500 })
      )
    );

    render(<ReplayControls fixtureId="bahrain-2023-race" />);

    await waitFor(() => {
      expect(screen.getByTestId('replay-pause-btn')).not.toBeDisabled();
    });

    await user.click(screen.getByTestId('replay-pause-btn'));

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Failed to pause replay');
  });

  it('shows error alert when stop request fails', async () => {
    const user = userEvent.setup();

    server.use(
      http.get('/api/v1/events/replay-status', () =>
        HttpResponse.json({ ...replayStatusFixture, status: 'running' })
      ),
      http.post('/api/v1/replay/:fixtureId/stop', () =>
        HttpResponse.json({ error: 'Server error' }, { status: 500 })
      )
    );

    render(<ReplayControls fixtureId="bahrain-2023-race" />);

    await waitFor(() => {
      expect(screen.getByTestId('replay-stop-btn')).not.toBeDisabled();
    });

    await user.click(screen.getByTestId('replay-stop-btn'));

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Failed to stop replay');
  });

  it('disables all replay control buttons while a lifecycle request is pending', async () => {
    const user = userEvent.setup();

    server.use(
      http.get('/api/v1/events/replay-status', () =>
        HttpResponse.json({ ...replayStatusFixture, status: 'idle' })
      ),
      http.post('/api/v1/replay/:fixtureId/start', async ({ request }) => {
        await delay(220);
        const body = await request.json();
        return HttpResponse.json({
          ...replayStatusFixture,
          status: 'running',
          speed_multiplier: body.speed_multiplier ?? 1,
          message: 'Replay started'
        });
      })
    );

    render(<ReplayControls fixtureId="bahrain-2023-race" />);

    await waitFor(() => {
      expect(screen.getByTestId('replay-start-btn')).not.toBeDisabled();
    });

    await user.click(screen.getByTestId('replay-start-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('replay-start-btn')).toBeDisabled();
      expect(screen.getByTestId('replay-pause-btn')).toBeDisabled();
      expect(screen.getByTestId('replay-stop-btn')).toBeDisabled();
      expect(screen.getByTestId('replay-speed-1x')).toBeDisabled();
      expect(screen.getByTestId('replay-speed-5x')).toBeDisabled();
      expect(screen.getByTestId('replay-speed-20x')).toBeDisabled();
      expect(screen.getByTestId('replay-speed-100x')).toBeDisabled();
    });

    await waitFor(() => {
      expect(screen.getByTestId('replay-status')).toHaveTextContent('running');
    });
  });
});
