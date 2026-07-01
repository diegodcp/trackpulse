import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { CircuitMap } from './CircuitMap';
import bahrainCircuit from '../fixtures/bahrainCircuit';

describe('TP-BH-0012 Bahrain circuit map', () => {
  it('renders expected segment count', () => {
    render(<CircuitMap circuit={bahrainCircuit} activeLayer="Track Temp" />);

    const segmentButtons = screen.getAllByRole('button');
    expect(segmentButtons).toHaveLength(16);
  });

  it('renders circuit SVG with correct dimensions', () => {
    render(<CircuitMap circuit={bahrainCircuit} activeLayer="Track Temp" />);

    const svg = screen.getByRole('img', { name: /Circuit map with 16 segments/ });
    const geometryTransform = screen.getByTestId('circuit-geometry-transform');
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveAttribute('viewBox', '0 0 1200 700');
    expect(geometryTransform).toHaveAttribute(
      'transform',
      expect.stringContaining('translate(600 350) rotate(90) scale(-1 1)')
    );
    expect(screen.getByText('Derived from OpenF1 location telemetry, single lap, smoothed.')).toBeInTheDocument();
  });

  it('displays tooltip on hover', async () => {
    const user = userEvent.setup();
    render(<CircuitMap circuit={bahrainCircuit} activeLayer="Track Temp" />);

    const startFinishSegment = screen.getByLabelText(/Start\/Finish Straight segment/);

    await user.hover(startFinishSegment);

    expect(screen.getByText('Start/Finish Straight')).toBeInTheDocument();
    expect(screen.getByText('Segment ID: bh-s01')).toBeInTheDocument();
    expect(screen.getByText('Sector 1')).toBeInTheDocument();
    expect(screen.getByText('Type: straight')).toBeInTheDocument();
    expect(screen.getByText('Wind Dir (Measured): -- deg')).toBeInTheDocument();
    expect(screen.getByText('Projection (Derived): unknown')).toBeInTheDocument();
  });

  it('applies active layer class to segments', () => {
    const { rerender } = render(
      <CircuitMap circuit={bahrainCircuit} activeLayer="Track Temp" />
    );

    let segments = screen.getAllByRole('button');
    expect(segments[0]).toHaveClass('layer-track-temp');

    rerender(<CircuitMap circuit={bahrainCircuit} activeLayer="Grip" />);

    segments = screen.getAllByRole('button');
    expect(segments[0]).toHaveClass('layer-grip');
  });

  it('renders wind arrows only when wind layer is active', () => {
    const { rerender } = render(
      <CircuitMap
        circuit={bahrainCircuit}
        activeLayer="Track Temp"
        windDirectionDeg={310}
        windSpeedMs={2.7}
      />
    );

    expect(screen.queryByLabelText('Wind layer arrows (derived)')).not.toBeInTheDocument();

    rerender(
      <CircuitMap
        circuit={bahrainCircuit}
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
    render(<CircuitMap circuit={bahrainCircuit} activeLayer="Track Temp" />);

    const t1Segment = screen.getByLabelText(/T1 Braking Zone segment in sector 1/);
    expect(t1Segment).toBeInTheDocument();
  });

  it('segments are keyboard accessible', async () => {
    const user = userEvent.setup();
    render(<CircuitMap circuit={bahrainCircuit} activeLayer="Track Temp" />);

    const startFinishSegment = screen.getByLabelText(/Start\/Finish Straight segment/);

    await user.tab();

    expect(startFinishSegment).toHaveFocus();
  });

  it('updates tooltip on keyboard focus', async () => {
    const user = userEvent.setup();
    render(<CircuitMap circuit={bahrainCircuit} activeLayer="Track Temp" />);

    const t1Segment = screen.getByLabelText(/T1 Braking Zone segment/);

    await user.tab();
    await user.tab(); // Move to T1

    expect(screen.getByText('T1 Braking Zone')).toBeInTheDocument();
  });

  it('shows derived wind class in segment tooltip', async () => {
    const user = userEvent.setup();
    render(
      <CircuitMap
        circuit={bahrainCircuit}
        activeLayer="Wind"
        windDirectionDeg={310}
        windSpeedMs={2.7}
      />
    );

    const startFinishSegment = screen.getByLabelText(/Start\/Finish Straight segment/);

    await user.hover(startFinishSegment);

    expect(screen.getByText(/Projection \(Derived\): (headwind|tailwind|crosswind left|crosswind right)/)).toBeInTheDocument();
  });

  it('applies traffic score metadata when traffic layer is active', () => {
    render(
      <CircuitMap
        circuit={bahrainCircuit}
        activeLayer="Traffic"
        segmentStates={[
          {
            segment_id: 'bh-s01',
            direction_deg: 162,
            measured: {
              wind_direction_deg: 310,
              wind_speed_ms: 2.7,
              truth_label: 'measured'
            },
            derived: {
              wind_relative_angle_deg: 148,
              wind_class: 'crosswind_right',
              wind_strength_score: 27,
              traffic_score: 82,
              traffic_truth_label: 'derived',
              truth_label: 'derived'
            }
          }
        ]}
      />
    );

    const startFinishSegment = screen.getByLabelText(/Start\/Finish Straight segment/);
    expect(startFinishSegment).toHaveAttribute('data-derived-traffic-score', '82.0');
    expect(startFinishSegment).toHaveAttribute('data-derived-traffic-truth-label', 'derived');
  });

  it('shows traffic derived values in segment tooltip', async () => {
    const user = userEvent.setup();
    render(
      <CircuitMap
        circuit={bahrainCircuit}
        activeLayer="Traffic"
        segmentStates={[
          {
            segment_id: 'bh-s01',
            direction_deg: 162,
            measured: {
              wind_direction_deg: 310,
              wind_speed_ms: 2.7,
              truth_label: 'measured'
            },
            derived: {
              wind_relative_angle_deg: 148,
              wind_class: 'crosswind_right',
              wind_strength_score: 27,
              traffic_score: 61.5,
              traffic_truth_label: 'derived',
              truth_label: 'derived'
            }
          }
        ]}
      />
    );

    const startFinishSegment = screen.getByLabelText(/Start\/Finish Straight segment/);
    await user.hover(startFinishSegment);

    expect(screen.getByText('Traffic (Derived): 61.5')).toBeInTheDocument();
    expect(screen.getByText('Traffic Truth: derived')).toBeInTheDocument();
  });

  it('renders corner evolution overlay when layer is active', () => {
    render(
      <CircuitMap
        circuit={bahrainCircuit}
        activeLayer="Corner Evolution"
        segmentStates={[
          {
            segment_id: 'bh-s01',
            direction_deg: 162,
            measured: {
              wind_direction_deg: 310,
              wind_speed_ms: 2.7,
              truth_label: 'measured'
            },
            derived: {
              wind_relative_angle_deg: 148,
              wind_class: 'crosswind_right',
              wind_strength_score: 27,
              truth_label: 'derived'
            },
            inferred: {
              evolution: 'improving',
              avg_speed_delta_kmh: 1.25,
              confidence: 0.82,
              truth_label: 'inferred'
            }
          }
        ]}
      />
    );

    expect(screen.getByLabelText('Corner evolution layer (inferred)')).toBeInTheDocument();
    const overlayPath = document.querySelector('[data-segment-id="bh-s01"]');
    expect(overlayPath).toHaveAttribute('data-evolution-direction', 'improving');
  });

  it('uses neutral corner evolution state when inferred data is missing', () => {
    render(
      <CircuitMap
        circuit={bahrainCircuit}
        activeLayer="Corner Evolution"
        segmentStates={[]}
      />
    );

    const overlayPath = document.querySelector('[data-segment-id="bh-s01"]');
    expect(overlayPath).toHaveAttribute('data-evolution-direction', 'insufficient_data');
  });

  it('shows corner evolution inferred fields in segment tooltip', async () => {
    const user = userEvent.setup();
    render(
      <CircuitMap
        circuit={bahrainCircuit}
        activeLayer="Corner Evolution"
        segmentStates={[
          {
            segment_id: 'bh-s01',
            direction_deg: 162,
            measured: {
              wind_direction_deg: 310,
              wind_speed_ms: 2.7,
              truth_label: 'measured'
            },
            derived: {
              wind_relative_angle_deg: 148,
              wind_class: 'crosswind_right',
              wind_strength_score: 27,
              truth_label: 'derived'
            },
            inferred: {
              evolution: 'worsening',
              avg_speed_delta_kmh: -0.8,
              confidence: 0.35,
              truth_label: 'inferred'
            }
          }
        ]}
      />
    );

    const startFinishSegment = screen.getByLabelText(/Start\/Finish Straight segment/);
    await user.hover(startFinishSegment);

    expect(screen.getByText('Evolution (Inferred): worsening')).toBeInTheDocument();
    expect(screen.getByText('Speed Delta (Inferred): -0.8 km/h')).toBeInTheDocument();
    expect(screen.getByText('Confidence (Inferred): 35%')).toBeInTheDocument();
    expect(screen.getByText('Truth Label: Inferred')).toBeInTheDocument();
  });

  it('prefers backend segment wind projection values when available', async () => {
    const user = userEvent.setup();
    render(
      <CircuitMap
        circuit={bahrainCircuit}
        activeLayer="Wind"
        windDirectionDeg={310}
        windSpeedMs={2.7}
        segmentStates={[
          {
            segment_id: 'bh-s01',
            direction_deg: 162,
            measured: {
              wind_direction_deg: 162,
              wind_speed_ms: 9.0,
              truth_label: 'measured'
            },
            derived: {
              wind_relative_angle_deg: 0,
              wind_class: 'headwind',
              wind_strength_score: 45,
              truth_label: 'derived'
            }
          }
        ]}
      />
    );

    const startFinishSegment = screen.getByLabelText(/Start\/Finish Straight segment/);
    await user.hover(startFinishSegment);

    expect(screen.getByText('Wind Dir (Measured): 162 deg')).toBeInTheDocument();
    expect(screen.getByText('Projection (Derived): headwind')).toBeInTheDocument();
  });

  it('segment paths render correctly', () => {
    render(<CircuitMap circuit={bahrainCircuit} activeLayer="Track Temp" />);

    const svgPaths = document.querySelectorAll('.segment');
    expect(svgPaths).toHaveLength(16);

    // Verify each segment has a path element
    svgPaths.forEach((path) => {
      expect(path).toHaveAttribute('d');
      expect(path).toHaveAttribute('role', 'button');
    });
  });

  it('matches regression snapshot and has non-empty segment paths', () => {
    const { container } = render(<CircuitMap circuit={bahrainCircuit} activeLayer="Track Temp" />);

    const segmentPaths = Array.from(container.querySelectorAll('.segment')).map(
      (path) => path.getAttribute('d') ?? ''
    );

    expect(segmentPaths).toHaveLength(16);
    segmentPaths.forEach((pathData) => {
      expect(pathData.trim().length).toBeGreaterThan(0);
    });
    expect(segmentPaths).toMatchSnapshot();
  });
});
