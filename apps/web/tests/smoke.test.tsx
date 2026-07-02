import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { App } from '../src/App';

describe('App', () => {
  it('renders without crashing', () => {
    render(<App />);
    expect(screen.getByText('TrackPulse')).toBeInTheDocument();
  });

  it('shows session selector when no session is selected', () => {
    render(<App />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });
});
