import windIcon from '../assets/wind_lines.svg';
import './LayerToggle.css';

export interface Layer {
  id: string;
  label: string;
  active: boolean;
  icon?: string;
}

interface LayerToggleProps {
  layers: Layer[];
  onToggle: (layerId: string) => void;
}

export function LayerToggle({ layers, onToggle }: LayerToggleProps) {
  return (
    <div className="layer-toggle" role="toolbar" aria-label="Map layers">
      {layers.map((layer) => (
        <button
          key={layer.id}
          className={`layer-btn ${layer.active ? 'layer-btn--active' : ''}`}
          onClick={() => onToggle(layer.id)}
          aria-pressed={layer.active}
          title={`${layer.active ? 'Hide' : 'Show'} ${layer.label} overlay`}
        >
          {layer.icon && (
            <img
              src={layer.icon}
              alt=""
              className="layer-btn__icon"
              aria-hidden="true"
            />
          )}
          <span>{layer.label}</span>
        </button>
      ))}
    </div>
  );
}

export { windIcon };
