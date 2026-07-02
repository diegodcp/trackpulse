import { Graphics } from 'pixi.js';
import type { CircuitGeometry } from '../types/circuit';
import type { Transform } from '../utils/coordinates';
import { worldToScreen } from '../utils/coordinates';

const SECTOR_COLORS: Record<number, number> = {
  1: 0xe10600, // Red (Sector 1)
  2: 0x0090d0, // Blue (Sector 2)
  3: 0xf5c211, // Yellow (Sector 3)
};
const TRACK_WIDTH = 6;
const TRACK_COLOR = 0x4a4a6a;
const SECTOR_MARKER_LENGTH = 14;
const SECTOR_MARKER_WIDTH = 3;

export function drawTrack(
  geometry: CircuitGeometry,
  transform: Transform,
): Graphics[] {
  // 1. Draw the full track in a neutral color
  const track = new Graphics();
  const firstPt = geometry.points[0];
  const { screenX: fx, screenY: fy } = worldToScreen(firstPt.x, firstPt.y, transform);
  track.moveTo(fx, fy);

  for (let i = 1; i < geometry.points.length; i++) {
    const point = geometry.points[i];
    const { screenX, screenY } = worldToScreen(point.x, point.y, transform);
    track.lineTo(screenX, screenY);
  }
  track.stroke({ width: TRACK_WIDTH, color: TRACK_COLOR, cap: 'round', join: 'round' });

  // 2. Draw sector boundary markers (perpendicular lines at sector transitions)
  const markers = new Graphics();
  let prevSector = geometry.segments[0]?.sector;

  for (const segment of geometry.segments) {
    if (segment.sector !== prevSector) {
      // Draw a perpendicular marker at the sector boundary
      const point = geometry.points[segment.start_idx];
      const nextPoint = geometry.points[Math.min(segment.start_idx + 1, geometry.points.length - 1)];
      const color = SECTOR_COLORS[segment.sector] ?? 0xffffff;

      const { screenX: x1, screenY: y1 } = worldToScreen(point.x, point.y, transform);
      const { screenX: x2, screenY: y2 } = worldToScreen(nextPoint.x, nextPoint.y, transform);

      // Compute perpendicular direction
      const dx = x2 - x1;
      const dy = y2 - y1;
      const len = Math.sqrt(dx * dx + dy * dy) || 1;
      const nx = -dy / len; // perpendicular
      const ny = dx / len;

      const half = SECTOR_MARKER_LENGTH / 2;
      markers.moveTo(x1 + nx * half, y1 + ny * half);
      markers.lineTo(x1 - nx * half, y1 - ny * half);
      markers.stroke({ width: SECTOR_MARKER_WIDTH, color, cap: 'round' });

      prevSector = segment.sector;
    }
  }

  return [track, markers];
}
