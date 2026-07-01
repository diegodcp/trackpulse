import { useEffect, useRef, useState } from 'react';

function lerp(start, end, progress) {
  return start + (end - start) * progress;
}

export function CarMarkerLayer({ markers, interpolationMs = 700, baseStrokeUnit = 10 }) {
  const [animatedMarkers, setAnimatedMarkers] = useState(markers);
  const frameRef = useRef(null);
  const timeoutRef = useRef(null);

  useEffect(() => {
    if (frameRef.current != null) {
      window.cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
    }
    if (timeoutRef.current != null) {
      window.clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }

    if (!markers || markers.length === 0) {
      setAnimatedMarkers([]);
      return undefined;
    }

    if (interpolationMs <= 0) {
      setAnimatedMarkers(markers);
      return undefined;
    }

    const startMarkersById = new Map(animatedMarkers.map((marker) => [marker.id, marker]));
    const animationStart = performance.now();

    const tick = (now) => {
      const elapsed = now - animationStart;
      const progress = Math.min(Math.max(elapsed / interpolationMs, 0), 1);

      const nextMarkers = markers.map((targetMarker) => {
        const startMarker = startMarkersById.get(targetMarker.id) ?? targetMarker;
        return {
          ...targetMarker,
          x: lerp(startMarker.x, targetMarker.x, progress),
          y: lerp(startMarker.y, targetMarker.y, progress)
        };
      });

      setAnimatedMarkers(nextMarkers);

      if (progress < 1) {
        frameRef.current = window.requestAnimationFrame(tick);
      }
    };

    frameRef.current = window.requestAnimationFrame(tick);
    timeoutRef.current = window.setTimeout(() => {
      setAnimatedMarkers(markers);
      timeoutRef.current = null;
    }, interpolationMs + 32);

    return () => {
      if (frameRef.current != null) {
        window.cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
      }
      if (timeoutRef.current != null) {
        window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, [markers, interpolationMs]);

  if (!animatedMarkers || animatedMarkers.length === 0) {
    return null;
  }

  const pingRadius = Number((baseStrokeUnit * 0.7).toFixed(2));
  const coreRadius = Number((baseStrokeUnit * 0.4).toFixed(2));
  const labelYOffset = Number((-baseStrokeUnit).toFixed(2));
  const labelFontSize = Number((baseStrokeUnit * 0.9).toFixed(2));
  const coreStrokeWidth = Number((baseStrokeUnit * 0.1).toFixed(2));

  return (
    <g className="replay-car-markers" aria-label="Replay car markers (approximate)">
      {animatedMarkers.map((marker) => (
        <g key={marker.id} transform={`translate(${marker.x}, ${marker.y})`} data-testid={marker.testId ?? undefined}>
          <circle r={pingRadius} className="replay-car-marker-ping" />
          <circle
            r={coreRadius}
            className="replay-car-marker-core"
            style={{ '--replay-car-core-stroke-width': coreStrokeWidth }}
          />
          <text
            y={labelYOffset}
            textAnchor="middle"
            className="replay-car-marker-label"
            style={{ '--replay-car-label-font-size': `${labelFontSize}px` }}
          >
            {marker.label}
          </text>
        </g>
      ))}
    </g>
  );
}
