export function TrackMapPanel({ activeLayer }) {
  return (
    <section className="track-map-panel" aria-label="Track map panel">
      <header className="track-map-header">
        <h2>Track Map</h2>
        <p>Active Layer: {activeLayer}</p>
      </header>
      <div className="track-map-placeholder" role="img" aria-label="Synthetic track map placeholder">
        Map rendering arrives in TP-FE-02
      </div>
    </section>
  );
}
