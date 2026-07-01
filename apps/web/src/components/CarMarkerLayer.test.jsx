import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { CarMarkerLayer } from './CarMarkerLayer';

describe('TP-BH-0014 CarMarkerLayer', () => {
  it('renders approximate replay car markers with driver labels', () => {
    render(
      <svg>
        <CarMarkerLayer
          markers={[
            { id: 'driver-1', label: '#1', x: 100, y: 120 },
            { id: 'driver-11', label: '#11', x: 180, y: 220 }
          ]}
        />
      </svg>
    );

    expect(screen.getByLabelText('Replay car markers (approximate)')).toBeInTheDocument();
    expect(screen.getByText('#1')).toBeInTheDocument();
    expect(screen.getByText('#11')).toBeInTheDocument();
  });

  it('interpolates marker movement between snapshot updates', async () => {
    const { rerender } = render(
      <svg>
        <CarMarkerLayer
          markers={[{ id: 'driver-1', label: '#1', x: 100, y: 120, testId: 'marker-driver-1' }]}
          interpolationMs={1}
        />
      </svg>
    );

    rerender(
      <svg>
        <CarMarkerLayer
          markers={[{ id: 'driver-1', label: '#1', x: 300, y: 320, testId: 'marker-driver-1' }]}
          interpolationMs={1}
        />
      </svg>
    );

    await waitFor(() => {
      expect(screen.getByTestId('marker-driver-1')).toHaveAttribute('transform', 'translate(300, 320)');
    });
  });
});
