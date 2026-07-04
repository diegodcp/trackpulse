import { Container, Graphics } from 'pixi.js';
import type { CircuitGeometry, CircuitSegment } from '../types/circuit';
import type { Transform } from '../utils/coordinates';
import { worldToScreen } from '../utils/coordinates';
import type { SegmentWind } from '../utils/windUtils';
import { windClassColor, windClassLabel, windIntensity } from '../utils/windUtils';

const ARROW_MIN_SIZE = 12;
const ARROW_MAX_SIZE = 20;
const ARROW_ALPHA = 0.92;
/** Offset distance in screen pixels — pushes icons outside the track */
const TRACK_OFFSET_PX = 16;
/** Extra hit area padding around arrows for easier hover */
const HIT_PADDING = 8;
/** Duration of rotation animation in ms */
const ROTATION_ANIM_MS = 600;

/** Previous rotation so we can animate between direction changes */
let lastBaseRotation: number | null = null;
/** Previous per-segment colors for smooth color transitions */
let lastSegmentColors: Map<number, number> = new Map();
/** Active animation frame id for cleanup */
let animFrameId: number | null = null;

/** Per-arrow metadata needed for redrawing during animation */
interface ArrowMeta {
  halfLen: number;
  headLen: number;
  headWidth: number;
  startColor: number;
  targetColor: number;
  segmentId: number;
}

/**
 * Compute shortest signed angular delta between two radian angles.
 * Returns a value in [-π, π].
 */
function shortestAngleDelta(from: number, to: number): number {
  let delta = (to - from) % (2 * Math.PI);
  if (delta > Math.PI) delta -= 2 * Math.PI;
  if (delta < -Math.PI) delta += 2 * Math.PI;
  return delta;
}

/**
 * Ease-out cubic for smooth deceleration.
 */
function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

/**
 * Linearly interpolate between two hex colors (0xRRGGBB).
 */
function lerpColor(from: number, to: number, t: number): number {
  const r1 = (from >> 16) & 0xff;
  const g1 = (from >> 8) & 0xff;
  const b1 = from & 0xff;
  const r2 = (to >> 16) & 0xff;
  const g2 = (to >> 8) & 0xff;
  const b2 = to & 0xff;
  const r = Math.round(r1 + (r2 - r1) * t);
  const g = Math.round(g1 + (g2 - g1) * t);
  const b = Math.round(b1 + (b2 - b1) * t);
  return (r << 16) | (g << 8) | b;
}

/**
 * Redraw an arrow graphic with a given color (clears and redraws geometry).
 */
function redrawArrow(arrow: Graphics, meta: ArrowMeta, color: number): void {
  arrow.clear();
  // Arrow head
  arrow.moveTo(meta.halfLen, 0);
  arrow.lineTo(meta.halfLen - meta.headLen, -meta.headWidth);
  arrow.lineTo(meta.halfLen - meta.headLen, meta.headWidth);
  arrow.closePath();
  arrow.fill({ color, alpha: ARROW_ALPHA });
  // Arrow shaft
  arrow.moveTo(-meta.halfLen * 0.5, 0);
  arrow.lineTo(meta.halfLen - meta.headLen, 0);
  arrow.stroke({ width: 2.5, color, alpha: ARROW_ALPHA });
}

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

    // Use a quarter-segment lookahead for a stable tangent direction at the midpoint.
    // A tiny lookahead (e.g. 5 points) gives sub-pixel differences → unstable perpendicular.
    const segmentSpan = segment.end_idx - segment.start_idx;
    const lookahead = Math.max(Math.floor(segmentSpan / 4), 10);
    const prevIdx = Math.max(midIdx - lookahead, segment.start_idx);
    const nextIdx = Math.min(midIdx + lookahead, segment.end_idx);
    const prevPoint = geometry.points[prevIdx];
    const nextPoint = geometry.points[nextIdx];

    const screenMid = worldToScreen(point.x, point.y, transform);
    const screenPrev = worldToScreen(prevPoint.x, prevPoint.y, transform);
    const screenNext = worldToScreen(nextPoint.x, nextPoint.y, transform);

    // Track tangent in screen space (from prev to next across the midpoint)
    const tdx = screenNext.screenX - screenPrev.screenX;
    const tdy = screenNext.screenY - screenPrev.screenY;
    const tLen = Math.sqrt(tdx * tdx + tdy * tdy) || 1;

    // Perpendicular (right-hand normal → points outside for most circuits)
    const nx = -tdy / tLen;
    const ny = tdx / tLen;

    // Offset position outside the track
    const ox = screenMid.screenX + nx * TRACK_OFFSET_PX;
    const oy = screenMid.screenY + ny * TRACK_OFFSET_PX;

    const intensity = windIntensity(sw.effective_speed);
    if (intensity < 0.02) continue;

    const targetColor = windClassColor(sw.wind_class);
    const startColor = lastSegmentColors.get(sw.segment_id) ?? targetColor;
    const size = ARROW_MIN_SIZE + intensity * (ARROW_MAX_SIZE - ARROW_MIN_SIZE);

    // --- Draw arrow with initial color (start of transition) ---
    const arrow = new Graphics();
    const halfLen = size / 2;
    const headLen = halfLen * 0.65;
    const headWidth = halfLen * 0.55;

    const meta: ArrowMeta = { halfLen, headLen, headWidth, startColor, targetColor, segmentId: sw.segment_id };
    (arrow as any).__windMeta = meta;

    // Draw with start color (will be animated to target)
    redrawArrow(arrow, meta, startColor);

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

    // Start at old rotation; will be animated to target
    arrow.rotation = lastBaseRotation ?? baseRotation;
    arrow.position.set(ox, oy);
    container.addChild(arrow);
  }

  // Animate rotation and color if wind direction/class changed
  if (animFrameId !== null) {
    cancelAnimationFrame(animFrameId);
    animFrameId = null;
  }

  const startRotation = lastBaseRotation ?? baseRotation;
  const rotationDelta = shortestAngleDelta(startRotation, baseRotation);
  const needsRotation = Math.abs(rotationDelta) > 0.01;

  // Check if any arrow needs a color transition
  const arrows = container.children as Graphics[];
  const needsColor = arrows.some((child) => {
    const meta = (child as any).__windMeta as ArrowMeta | undefined;
    return meta && meta.startColor !== meta.targetColor;
  });

  const needsAnimation = needsRotation || needsColor;

  if (needsAnimation) {
    const startTime = performance.now();

    function animate() {
      const elapsed = performance.now() - startTime;
      const progress = Math.min(elapsed / ROTATION_ANIM_MS, 1);
      const eased = easeOutCubic(progress);

      // Rotation interpolation
      const currentRotation = startRotation + rotationDelta * eased;

      for (const child of arrows) {
        child.rotation = currentRotation;

        // Color interpolation — redraw each arrow with lerped color
        const meta = (child as any).__windMeta as ArrowMeta | undefined;
        if (meta && meta.startColor !== meta.targetColor) {
          const currentColor = lerpColor(meta.startColor, meta.targetColor, eased);
          redrawArrow(child, meta, currentColor);
        }
      }

      if (progress < 1) {
        animFrameId = requestAnimationFrame(animate);
      } else {
        animFrameId = null;
      }
    }

    animFrameId = requestAnimationFrame(animate);
  }

  // Update stored state for next transition
  lastBaseRotation = baseRotation;
  const newColors = new Map<number, number>();
  for (const child of arrows) {
    const meta = (child as any).__windMeta as ArrowMeta | undefined;
    if (meta) newColors.set(meta.segmentId, meta.targetColor);
  }
  lastSegmentColors = newColors;

  // Cancel animation when container is destroyed
  const prevDestroyed = container.listenerCount('destroyed') > 0;
  if (!prevDestroyed) {
    container.on('destroyed', () => {
      if (animFrameId !== null) {
        cancelAnimationFrame(animFrameId);
        animFrameId = null;
      }
    });
  }

  return container;
}
