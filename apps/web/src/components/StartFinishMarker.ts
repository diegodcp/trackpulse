import { Graphics } from 'pixi.js';
import type { CircuitPoint } from '../types/circuit';
import type { Transform } from '../utils/coordinates';
import { worldToScreen } from '../utils/coordinates';

const MARKER_COLOR = 0xffffff;
const MARKER_LENGTH = 20;
const MARKER_WIDTH = 4;

export function drawStartFinish(
  point: CircuitPoint,
  transform: Transform,
): Graphics {
  const g = new Graphics();
  const { screenX, screenY } = worldToScreen(point.x, point.y, transform);

  g.moveTo(screenX - MARKER_LENGTH / 2, screenY);
  g.lineTo(screenX + MARKER_LENGTH / 2, screenY);
  g.stroke({ width: MARKER_WIDTH, color: MARKER_COLOR });

  // Small circle at start/finish
  g.circle(screenX, screenY, 5);
  g.fill({ color: MARKER_COLOR });

  return g;
}
