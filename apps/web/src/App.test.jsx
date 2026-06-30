import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { App } from './App';

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
