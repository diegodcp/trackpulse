import { Container, Graphics } from 'pixi.js';
import type { CircuitGeometry, CircuitSegment } from '../types/circuit';
import type { Transform } from '../utils/coordinates';
import { worldToScreen } from '../utils/coordinates';
import type { SegmentWind } from '../utils/windUtils';
import { windClassColor, windClassLabel, windIntensity } from '../utils/windUtils';

const ARROW_MIN_SIZE = 10;
const ARROW_MAX_SIZE = 18;
const ARROW_ALPHA = 0.92;
/** Offset distance in screen pixels — pushes icons outside the track */
const TRACK_OFFSET_PX = 12;
/** Extra hit area padding around arrows for easier hover */
const HIT_PADDING = 6;

/**
 * Build a human-readable tooltip string for a segment's wind.
 */
function buildTooltip(sw: SegmentWind, segmentId: number): string {
  const label = windClassLabel(sw.wind_class);
  const speed = sw.effective_speed.toFixed(1);

  let description: string;
  switch (sw.wind_class) {
    case 'headwind':
      description = 'Wind opposes car direction — increases drag, reduces top speed';
      break;
    case 'tailwind':
      description = 'Wind assists car direction — reduces drag, boosts straight-line speed';
      break;
    case 'crosswind_left':
      description = 'Lateral wind from left — destabilises car, affects cornering';
      break;
    case 'crosswind_right':
      description = 'Lateral wind from right — destabilises car, affects cornering';
      break;
    default:
      description = '';
  }

  return `Segment ${segmentId + 1}: ${label}\nEffective: ${speed} m/s\n${description}`;
}

/**
 * Draw wind arrows at segment midpoints, offset outside the track.
 *
 * Each arrow shows the direction wind is GOING, color-coded:
 * - Red = headwind (wind opposes car travel direction — slows cars)
 * - Green = tailwind (wind pushes cars in travel direction — assists speed)
 * - Orange = crosswind (lateral wind — destabilises cars)
 *
 * Hovering over an arrow shows a tooltip with the wind classification,
 * effective speed, and a description of what it means for the cars.
 */
export function drawWindIcons(
  geometry: CircuitGeometry,
  segmentWind: SegmentWind[],
  windDirection: number,
  transform: Transform,
): Container {
  const container = new Container();
  container.label = 'wind-overlay';

  // Create a shared tooltip DOM element (reused across arrows)
  let tooltip: HTMLDivElement | null = null;

  function getTooltip(): HTMLDivElement {
    if (tooltip) return tooltip;
    tooltip = document.getElementById('wind-tooltip') as HTMLDivElement | null;
    if (!tooltip) {
      tooltip = document.createElement('div');
      tooltip.id = 'wind-tooltip';
      tooltip.style.cssText = `
        position: fixed;
        pointer-events: none;
        background: rgba(20, 20, 40, 0.92);
        color: #eee;
        font-size: 12px;
        line-height: 1.4;
        padding: 6px 10px;
        border-radius: 4px;
        border: 1px solid #555;
        white-space: pre-line;
        z-index: 1000;
        display: none;
        max-width: 260px;
      `;
      document.body.appendChild(tooltip);
    }
    return tooltip;
  }

  // Cleanup tooltip when container is destroyed
  container.on('destroyed', () => {
    const el = document.getElementById('wind-tooltip');
    if (el) el.style.display = 'none';
  });

  // Compute screen-space rotation for arrow direction.
  const windGoingDeg = (windDirection + 180) % 360;
  const baseRotation = (windGoingDeg - 90) * (Math.PI / 180);

  for (const sw of segmentWind) {
    const segment = geometry.segments.find((s: CircuitSegment) => s.id === sw.segment_id);
    if (!segment) continue;

    const midIdx = Math.floor((segment.start_idx + segment.end_idx) / 2);
    const point = geometry.points[midIdx];
    if (!point) continue;

    // Compute track direction at midpoint to find the perpendicular (for offset)
    const nextIdx = Math.min(midIdx + 5, geometry.points.length - 1);
    const nextPoint = geometry.points[nextIdx];
    const screenMid = worldToScreen(point.x, point.y, transform);
    const screenNext = worldToScreen(nextPoint.x, nextPoint.y, transform);

    // Track tangent in screen space
    const tdx = screenNext.screenX - screenMid.screenX;
    const tdy = screenNext.screenY - screenMid.screenY;
    const tLen = Math.sqrt(tdx * tdx + tdy * tdy) || 1;

    // Perpendicular (right-hand normal → points outside for most circuits)
    const nx = -tdy / tLen;
    const ny = tdx / tLen;

    // Offset position outside the track
    const ox = screenMid.screenX + nx * TRACK_OFFSET_PX;
    const oy = screenMid.screenY + ny * TRACK_OFFSET_PX;

    const intensity = windIntensity(sw.effective_speed);
    if (intensity < 0.02) continue;

    const color = windClassColor(sw.wind_class);
    const size = ARROW_MIN_SIZE + intensity * (ARROW_MAX_SIZE - ARROW_MIN_SIZE);

    // --- Draw arrow only (no circle) ---
    const arrow = new Graphics();
    const halfLen = size / 2;
    const headLen = halfLen * 0.65;
    const headWidth = halfLen * 0.55;

    // Arrow head (filled triangle, drawn pointing right → rotated)
    arrow.moveTo(halfLen, 0);
    arrow.lineTo(halfLen - headLen, -headWidth);
    arrow.lineTo(halfLen - headLen, headWidth);
    arrow.closePath();
    arrow.fill({ color, alpha: ARROW_ALPHA });

    // Arrow shaft
    arrow.moveTo(-halfLen * 0.5, 0);
    arrow.lineTo(halfLen - headLen, 0);
    arrow.stroke({ width: 2.5, color, alpha: ARROW_ALPHA });

    // --- Make arrow interactive for tooltip ---
    arrow.eventMode = 'static';
    arrow.cursor = 'pointer';
    // Expand hit area for easier hover
    arrow.hitArea = {
      contains: (x: number, y: number) => {
        const pad = halfLen + HIT_PADDING;
        return x >= -pad && x <= pad && y >= -pad && y <= pad;
      },
    };

    const tooltipText = buildTooltip(sw, sw.segment_id);

    arrow.on('pointerover', (e) => {
      const tip = getTooltip();
      tip.textContent = tooltipText;
      tip.style.display = 'block';
      tip.style.left = `${e.globalX + 12}px`;
      tip.style.top = `${e.globalY - 10}px`;
    });

    arrow.on('pointermove', (e) => {
      const tip = getTooltip();
      tip.style.left = `${e.globalX + 12}px`;
      tip.style.top = `${e.globalY - 10}px`;
    });

    arrow.on('pointerout', () => {
      const tip = getTooltip();
      tip.style.display = 'none';
    });

    arrow.rotation = baseRotation;
    arrow.position.set(ox, oy);
    container.addChild(arrow);
  }

  return container;
}
