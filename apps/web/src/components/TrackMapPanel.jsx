import { useState, useEffect } from 'react';
import { CircuitMap } from './CircuitMap';
import circuitData from '../data/circuit-fixture.json';

export function TrackMapPanel({ activeLayer }) {
  const [circuit, setCircuit] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Simulate loading the circuit fixture
    setCircuit(circuitData);
    setIsLoading(false);
  }, []);

  if (isLoading) {
    return (
      <section className="track-map-panel" aria-label="Track map panel">
        <div className="track-map-loading">Loading track map...</div>
      </section>
    );
  }

  return (
    <section className="track-map-panel" aria-label="Track map panel">
      <header className="track-map-header">
        <h2>Track Map</h2>
        <p>Active Layer: {activeLayer}</p>
      </header>
      <CircuitMap circuit={circuit} activeLayer={activeLayer} />
    </section>
  );
}
