import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { App } from '../src/App';

describe('App', () => {
  it('renders without crashing', () => {
    render(<App />);
    expect(screen.getByText('TrackPulse')).toBeInTheDocument();
  });

  it('shows initial placeholder message', () => {
    render(<App />);
    expect(screen.getByText('Select a session to begin')).toBeInTheDocument();
  });
});
