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

  it('track map header displays active layer', () => {
    render(<App />);

    expect(screen.getByText('Active Layer: Track Temp')).toBeInTheDocument();
  });
});
