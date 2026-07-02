import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PlaybackControlsBar } from '../src/components/PlaybackControls';
import type { PlaybackControls } from '../src/hooks/usePlayback';

function makeMockPlayback(overrides: Partial<PlaybackControls> = {}): PlaybackControls {
  return {
    state: 'paused',
    currentTime: 0,
    duration: 5520,
    speed: 1,
    currentLap: null,
    play: vi.fn(),
    pause: vi.fn(),
    setSpeed: vi.fn(),
    seekTo: vi.fn(),
    seekRelative: vi.fn(),
    ...overrides,
  };
}

describe('PlaybackControlsBar', () => {
  it('shows play button when paused', () => {
    const playback = makeMockPlayback({ state: 'paused' });
    render(<PlaybackControlsBar playback={playback} disabled={false} />);
    expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
  });

  it('shows pause button when playing', () => {
    const playback = makeMockPlayback({ state: 'playing' });
    render(<PlaybackControlsBar playback={playback} disabled={false} />);
    expect(screen.getByRole('button', { name: /pause/i })).toBeInTheDocument();
  });

  it('disables controls when disabled prop is true', () => {
    const playback = makeMockPlayback({ state: 'paused' });
    render(<PlaybackControlsBar playback={playback} disabled={true} />);
    expect(screen.getByRole('button', { name: /play/i })).toBeDisabled();
    expect(screen.getByRole('combobox', { name: /speed/i })).toBeDisabled();
    expect(screen.getByRole('slider', { name: /timeline/i })).toBeDisabled();
  });

  it('disables controls in idle state', () => {
    const playback = makeMockPlayback({ state: 'idle' });
    render(<PlaybackControlsBar playback={playback} disabled={false} />);
    expect(screen.getByRole('button', { name: /play/i })).toBeDisabled();
  });

  it('displays formatted time', () => {
    const playback = makeMockPlayback({ currentTime: 125, duration: 5520 });
    render(<PlaybackControlsBar playback={playback} disabled={false} />);
    expect(screen.getByText('02:05 / 1:32:00')).toBeInTheDocument();
  });

  it('calls play when play button clicked', async () => {
    const user = userEvent.setup();
    const playback = makeMockPlayback({ state: 'paused' });
    render(<PlaybackControlsBar playback={playback} disabled={false} />);

    await user.click(screen.getByRole('button', { name: /play/i }));
    expect(playback.play).toHaveBeenCalledOnce();
  });

  it('calls pause when pause button clicked', async () => {
    const user = userEvent.setup();
    const playback = makeMockPlayback({ state: 'playing' });
    render(<PlaybackControlsBar playback={playback} disabled={false} />);

    await user.click(screen.getByRole('button', { name: /pause/i }));
    expect(playback.pause).toHaveBeenCalledOnce();
  });

  it('calls setSpeed on speed change', async () => {
    const user = userEvent.setup();
    const playback = makeMockPlayback({ state: 'paused' });
    render(<PlaybackControlsBar playback={playback} disabled={false} />);

    await user.selectOptions(screen.getByRole('combobox', { name: /speed/i }), '10');
    expect(playback.setSpeed).toHaveBeenCalledWith(10);
  });

  it('shows lap indicator when currentLap is set', () => {
    const playback = makeMockPlayback({ currentLap: 15 });
    render(<PlaybackControlsBar playback={playback} disabled={false} />);
    expect(screen.getByText('Lap 15')).toBeInTheDocument();
  });

  it('hides lap indicator when currentLap is null', () => {
    const playback = makeMockPlayback({ currentLap: null });
    render(<PlaybackControlsBar playback={playback} disabled={false} />);
    expect(screen.queryByText(/Lap/)).not.toBeInTheDocument();
  });
});
