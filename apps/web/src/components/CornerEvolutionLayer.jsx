const NEUTRAL_EVOLUTION = 'insufficient_data';

const KNOWN_EVOLUTION_DIRECTIONS = new Set([
  'improving',
  'stable',
  'worsening',
  NEUTRAL_EVOLUTION
]);

const EVOLUTION_STYLES = {
  improving: {
    stroke: '#2ecc71',
    opacity: 0.88,
    strokeWidth: 13
  },
  stable: {
    stroke: '#f4d35e',
    opacity: 0.72,
    strokeWidth: 11
  },
  worsening: {
    stroke: '#e74c3c',
    opacity: 0.88,
    strokeWidth: 13
  },
  insufficient_data: {
    stroke: '#a3a3a3',
    opacity: 0.36,
    strokeWidth: 9
  }
};

function clampConfidence(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return null;
  }

  return Math.max(0, Math.min(1, value));
}

function normalizeEvolutionDirection(value) {
  if (typeof value !== 'string') {
    return NEUTRAL_EVOLUTION;
  }

  return KNOWN_EVOLUTION_DIRECTIONS.has(value) ? value : NEUTRAL_EVOLUTION;
}

function normalizeTruthLabel(value) {
  if (typeof value !== 'string') {
    return 'Inferred';
  }

  return value.trim().toLowerCase() === 'inferred' ? 'Inferred' : value;
}

export function getCornerEvolutionState(segmentState) {
  const inferredState = segmentState?.inferred ?? null;
  const evolutionDirection = normalizeEvolutionDirection(inferredState?.evolution);
  const speedDeltaKmh =
    typeof inferredState?.avg_speed_delta_kmh === 'number' && !Number.isNaN(inferredState.avg_speed_delta_kmh)
      ? inferredState.avg_speed_delta_kmh
      : null;
  const confidence = clampConfidence(inferredState?.confidence);
  const truthLabel = normalizeTruthLabel(inferredState?.truth_label);

  return {
    evolutionDirection,
    speedDeltaKmh,
    confidence,
    truthLabel,
    style: EVOLUTION_STYLES[evolutionDirection] ?? EVOLUTION_STYLES[NEUTRAL_EVOLUTION]
  };
}

export function CornerEvolutionLayer({ activeLayer, segments, segmentStateById }) {
  if (activeLayer !== 'Corner Evolution') {
    return null;
  }

  return (
    <g className="corner-evolution-overlay" aria-label="Corner evolution layer (inferred)">
      {segments.map((segment) => {
        const segmentState = getCornerEvolutionState(segmentStateById.get(segment.segmentId));
        const segmentPath = segment.path
          .map((point, idx) => `${idx === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
          .join(' ');

        return (
          <path
            key={`corner-evolution-${segment.segmentId}`}
            d={segmentPath}
            className="corner-evolution-path"
            fill="none"
            strokeLinecap="round"
            style={segmentState.style}
            data-segment-id={segment.segmentId}
            data-evolution-direction={segmentState.evolutionDirection}
            data-evolution-confidence={
              segmentState.confidence == null ? 'unknown' : segmentState.confidence.toFixed(2)
            }
          />
        );
      })}
    </g>
  );
}