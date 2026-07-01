import { useState } from 'react';
import '../styles/circuit-map.css';

function normalizeAngleDeg(angleDeg) {
  return ((angleDeg + 180) % 360) - 180;
}

function getDerivedWindClass(relativeAngleDeg) {
  if (relativeAngleDeg === null || Number.isNaN(relativeAngleDeg)) {
    return 'unknown';
  }

  const absoluteAngle = Math.abs(relativeAngleDeg);
  if (absoluteAngle <= 30) {
    return 'headwind';
  }
  if (absoluteAngle >= 150) {
    return 'tailwind';
  }
  if (relativeAngleDeg < 0) {
    return 'crosswind_left';
  }
  return 'crosswind_right';
}

function buildWindProjection(segmentDirectionDeg, windDirectionDeg, windSpeedMs) {
  if (segmentDirectionDeg == null || windDirectionDeg == null || windSpeedMs == null) {
    return { windClass: 'unknown', relativeAngleDeg: null };
  }

  // Match backend convention: meteorological wind direction (from north, clockwise).
  const relativeAngleDeg = Number(normalizeAngleDeg(windDirectionDeg - segmentDirectionDeg).toFixed(1));
  return {
    windClass: getDerivedWindClass(relativeAngleDeg),
    relativeAngleDeg
  };
}

function formatWindClass(windClass) {
  return windClass.replace(/_/g, ' ');
}

function createWindArrows(width, height, windDirectionDeg) {
  const columns = 6;
  const rows = 4;
  const xStep = width / (columns + 1);
  const yStep = height / (rows + 1);

  return Array.from({ length: columns * rows }, (_, index) => {
    const column = index % columns;
    const row = Math.floor(index / columns);
    const x = Math.round((column + 1) * xStep);
    const y = Math.round((row + 1) * yStep);
    const delay = `${(index % 6) * 0.15}s`;

    return {
      id: `wind-arrow-${index}`,
      x,
      y,
      delay,
      rotateDeg: windDirectionDeg ?? 0
    };
  });
}

export function CircuitMap({
  circuit,
  activeLayer,
  windDirectionDeg = null,
  windSpeedMs = null,
  carMarkers = []
}) {
  const [hoveredSegment, setHoveredSegment] = useState(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  if (!circuit) {
    return (
      <div className="circuit-map-error" role="alert">
        No circuit data available
      </div>
    );
  }

  const { width, height, centerline, segments } = circuit;
  const windArrows = createWindArrows(width, height, windDirectionDeg);
  const showWindOverlay = activeLayer === 'Wind';
  const pathData = centerline
    .map((point, idx) => `${idx === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
    .join(' ');

  const handleSegmentMouseEnter = (segment, e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const svgRect = e.currentTarget.closest('svg').getBoundingClientRect();
    
    setHoveredSegment(segment);
    setTooltipPos({
      x: rect.left - svgRect.left + rect.width / 2,
      y: rect.top - svgRect.top - 10
    });
  };

  const handleSegmentMouseLeave = () => {
    setHoveredSegment(null);
  };

  const handleSegmentFocus = (segment, e) => {
    const svg = e.currentTarget.closest('svg');
    const svgRect = svg.getBoundingClientRect();
    
    setHoveredSegment(segment);
    setTooltipPos({
      x: svgRect.width / 2,
      y: -10
    });
  };

  return (
    <div className="circuit-map-container">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="xMidYMid meet"
        className="circuit-map-svg"
        role="img"
        aria-label={`Circuit map with ${segments.length} segments`}
      >
        {/* Centerline */}
        <path
          d={pathData}
          className="centerline"
          fill="none"
          stroke="currentColor"
          strokeWidth="4"
        />

        {/* Segment overlays */}
        {segments.map((segment) => {
          const windProjection = buildWindProjection(segment.dominantDirectionDeg, windDirectionDeg, windSpeedMs);
          const segmentPath = segment.path
            .map((point, idx) => `${idx === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
            .join(' ');

          return (
            <g key={segment.segmentId} className="segment-group">
              <path
                d={segmentPath}
                className={`segment segment-${segment.type} layer-${activeLayer.toLowerCase().replace(/\s+/g, '-')} ${
                  hoveredSegment?.segmentId === segment.segmentId ? 'is-hovered' : ''
                }`}
                fill="none"
                stroke="currentColor"
                strokeWidth="8"
                strokeLinecap="round"
                onMouseEnter={(e) => handleSegmentMouseEnter(segment, e)}
                onMouseLeave={handleSegmentMouseLeave}
                onFocus={(e) => handleSegmentFocus(segment, e)}
                role="button"
                tabIndex="0"
                aria-label={`${segment.label} segment in sector ${segment.sector}; derived wind class ${formatWindClass(windProjection.windClass)}`}
                data-derived-wind-class={windProjection.windClass}
              />
            </g>
          );
        })}

        {/* Wind layer overlay */}
        {showWindOverlay && (
          <g className="wind-overlay" aria-label="Wind layer arrows (derived)">
            {windArrows.map((arrow) => (
              <g
                key={arrow.id}
                transform={`translate(${arrow.x}, ${arrow.y}) rotate(${arrow.rotateDeg})`}
              >
                <g className="wind-arrow" style={{ animationDelay: arrow.delay }}>
                  <line x1="-10" y1="0" x2="8" y2="0" className="wind-arrow-shaft" />
                  <polyline points="3,-4 8,0 3,4" className="wind-arrow-head" />
                </g>
              </g>
            ))}
          </g>
        )}

        {/* Replay car markers (measured location projected to map space) */}
        {carMarkers.length > 0 && (
          <g className="replay-car-markers" aria-label="Replay car markers">
            {carMarkers.map((marker) => (
              <g
                key={marker.id}
                transform={`translate(${marker.x}, ${marker.y})`}
                data-testid={marker.testId ?? undefined}
              >
                <circle r="7" className="replay-car-marker-ping" />
                <circle r="4" className="replay-car-marker-core" />
                <text y="-10" textAnchor="middle" className="replay-car-marker-label">
                  {marker.label}
                </text>
              </g>
            ))}
          </g>
        )}

        {/* Tooltip */}
        {hoveredSegment && (
          <g className="tooltip" transform={`translate(${tooltipPos.x}, ${tooltipPos.y})`}>
            <rect
              x="-70"
              y="0"
              width="140"
              height="86"
              rx="4"
              className="tooltip-box"
            />
            <text x="0" y="18" className="tooltip-label" textAnchor="middle">
              {hoveredSegment.label}
            </text>
            <text x="0" y="38" className="tooltip-info" textAnchor="middle">
              Sector {hoveredSegment.sector}
            </text>
            <text x="0" y="58" className="tooltip-info" textAnchor="middle">
              {hoveredSegment.type.replace(/_/g, ' ')}
            </text>
            <text x="0" y="76" className="tooltip-info" textAnchor="middle">
              Wind (Derived): {formatWindClass(buildWindProjection(hoveredSegment.dominantDirectionDeg, windDirectionDeg, windSpeedMs).windClass)}
            </text>
          </g>
        )}
      </svg>
    </div>
  );
}
