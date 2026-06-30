export function LayerToggleBar({ layers, activeLayer, onLayerChange }) {
  return (
    <section className="layer-toggle" aria-label="Layer toggles">
      <h2>Layers</h2>
      <div className="layer-toggle-buttons" role="toolbar" aria-label="Track data layers">
        {layers.map((layer) => {
          const isActive = activeLayer === layer;

          return (
            <button
              key={layer}
              type="button"
              className={`layer-button ${isActive ? 'is-active' : ''}`}
              onClick={() => onLayerChange(layer)}
              aria-pressed={isActive}
            >
              {layer}
            </button>
          );
        })}
      </div>
    </section>
  );
}
