import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { CircuitMap } from './CircuitMap';
import circuitFixture from '../data/circuit-fixture.json';

describe('TP-FE-02 Synthetic circuit map', () => {
  it('renders expected segment count', () => {
    render(<CircuitMap circuit={circuitFixture} activeLayer="Track Temp" />);

    const segmentButtons = screen.getAllByRole('button');
    expect(segmentButtons).toHaveLength(12);
  });

  it('renders circuit SVG with correct dimensions', () => {
    render(<CircuitMap circuit={circuitFixture} activeLayer="Track Temp" />);

    const svg = screen.getByRole('img', { name: /Circuit map with 12 segments/ });
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveAttribute('viewBox', '0 0 1000 600');
  });

  it('displays tooltip on hover', async () => {
    const user = userEvent.setup();
    render(<CircuitMap circuit={circuitFixture} activeLayer="Track Temp" />);

    const startFinishSegment = screen.getByLabelText(/Start\/Finish segment/);

    await user.hover(startFinishSegment);

    expect(screen.getByText('Start/Finish')).toBeInTheDocument();
    expect(screen.getByText('Sector 1')).toBeInTheDocument();
    expect(screen.getByText('straight')).toBeInTheDocument();
  });

  it('applies active layer class to segments', () => {
    const { rerender } = render(
      <CircuitMap circuit={circuitFixture} activeLayer="Track Temp" />
    );

    let segments = screen.getAllByRole('button');
    expect(segments[0]).toHaveClass('layer-track-temp');

    rerender(<CircuitMap circuit={circuitFixture} activeLayer="Grip" />);

    segments = screen.getAllByRole('button');
    expect(segments[0]).toHaveClass('layer-grip');
  });

  it('renders wind arrows only when wind layer is active', () => {
    const { rerender } = render(
      <CircuitMap
        circuit={circuitFixture}
        activeLayer="Track Temp"
        windDirectionDeg={310}
        windSpeedMs={2.7}
      />
    );

    expect(screen.queryByLabelText('Wind layer arrows (derived)')).not.toBeInTheDocument();

    rerender(
      <CircuitMap
        circuit={circuitFixture}
        activeLayer="Wind"
        windDirectionDeg={310}
        windSpeedMs={2.7}
      />
    );

    expect(screen.getByLabelText('Wind layer arrows (derived)')).toBeInTheDocument();
  });

  it('shows error when circuit data is missing', () => {
    render(<CircuitMap circuit={null} activeLayer="Track Temp" />);

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('No circuit data available')).toBeInTheDocument();
  });

  it('segment labels contain sector and type information', () => {
    render(<CircuitMap circuit={circuitFixture} activeLayer="Track Temp" />);

    const t1Segment = screen.getByLabelText(/T1 Braking segment in sector 1/);
    expect(t1Segment).toBeInTheDocument();
  });

  it('segments are keyboard accessible', async () => {
    const user = userEvent.setup();
    render(<CircuitMap circuit={circuitFixture} activeLayer="Track Temp" />);

    const startFinishSegment = screen.getByLabelText(/Start\/Finish segment/);

    await user.tab();

    expect(startFinishSegment).toHaveFocus();
  });

  it('updates tooltip on keyboard focus', async () => {
    const user = userEvent.setup();
    render(<CircuitMap circuit={circuitFixture} activeLayer="Track Temp" />);

    const t1Segment = screen.getByLabelText(/T1 Braking segment/);

    await user.tab();
    await user.tab(); // Move to T1

    expect(screen.getByText('T1 Braking')).toBeInTheDocument();
  });

  it('shows derived wind class in segment tooltip', async () => {
    const user = userEvent.setup();
    render(
      <CircuitMap
        circuit={circuitFixture}
        activeLayer="Wind"
        windDirectionDeg={310}
        windSpeedMs={2.7}
      />
    );

    const startFinishSegment = screen.getByLabelText(/Start\/Finish segment/);

    await user.hover(startFinishSegment);

    expect(screen.getByText('Wind (Derived): headwind')).toBeInTheDocument();
  });

  it('segment paths render correctly', () => {
    render(<CircuitMap circuit={circuitFixture} activeLayer="Track Temp" />);

    const svgPaths = document.querySelectorAll('.segment');
    expect(svgPaths).toHaveLength(12);

    // Verify each segment has a path element
    svgPaths.forEach((path) => {
      expect(path).toHaveAttribute('d');
      expect(path).toHaveAttribute('role', 'button');
    });
  });
});
