import { CircuitMap } from '../components/CircuitMap';
import bahrainCircuit from '../fixtures/bahrainCircuit';

export function BahrainCircuitDemo() {
  return (
    <main style={{ padding: '1rem' }}>
      <section className="track-map-panel" aria-label="Bahrain map local demo">
        <header className="track-map-header">
          <h2>Bahrain Circuit Demo</h2>
          <p>Active Layer: Track Temp</p>
        </header>
        <p className="track-map-precision-note">
          Stylized Bahrain circuit. Approximate geometry only; no racing-line precision is claimed.
        </p>
        <CircuitMap circuit={bahrainCircuit} activeLayer="Track Temp" />
      </section>
    </main>
  );
}
