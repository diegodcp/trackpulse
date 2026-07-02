import { Graphics } from 'pixi.js';
import type { CircuitGeometry, CircuitSegment } from '../types/circuit';
import type { Transform } from '../utils/coordinates';
import { worldToScreen } from '../utils/coordinates';

const SECTOR_COLORS: Record<number, number> = {
  1: 0xe10600, // Red (Sector 1)
  2: 0x0090d0, // Blue (Sector 2)
  3: 0xf5c211, // Yellow (Sector 3)
};
const TRACK_WIDTH = 8;

export function drawTrack(
  geometry: CircuitGeometry,
  transform: Transform,
): Graphics[] {
  const graphics: Graphics[] = [];

  for (const segment of geometry.segments) {
    const g = drawSegment(geometry, segment, transform);
    graphics.push(g);
  }

  return graphics;
}

function drawSegment(
  geometry: CircuitGeometry,
  segment: CircuitSegment,
  transform: Transform,
): Graphics {
  const g = new Graphics();
  const color = SECTOR_COLORS[segment.sector] ?? 0xffffff;

  const firstPoint = geometry.points[segment.start_idx];
  const { screenX, screenY } = worldToScreen(firstPoint.x, firstPoint.y, transform);

  g.setStrokeStyle({ width: TRACK_WIDTH, color, cap: 'round', join: 'round' });
  g.moveTo(screenX, screenY);

  for (let i = segment.start_idx + 1; i <= segment.end_idx; i++) {
    const point = geometry.points[i];
    const { screenX: sx, screenY: sy } = worldToScreen(point.x, point.y, transform);
    g.lineTo(sx, sy);
  }

  g.stroke();
  return g;
}
