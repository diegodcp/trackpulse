import { useState } from 'react';
import '../styles/circuit-map.css';

export function CircuitMap({ circuit, activeLayer }) {
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
                aria-label={`${segment.label} segment in sector ${segment.sector}`}
              />
            </g>
          );
        })}

        {/* Tooltip */}
        {hoveredSegment && (
          <g className="tooltip" transform={`translate(${tooltipPos.x}, ${tooltipPos.y})`}>
            <rect
              x="-70"
              y="0"
              width="140"
              height="70"
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
          </g>
        )}
      </svg>
    </div>
  );
}
