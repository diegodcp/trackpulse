import type { CircuitBounds } from '../types/circuit';

export interface ViewportSize {
  width: number;
  height: number;
}

export interface Transform {
  scale: number;
  offsetX: number;
  offsetY: number;
}

/**
 * Compute the transform that maps world bounds into viewport with padding.
 * Maintains aspect ratio; centers the circuit in available space.
 */
export function computeTransform(
  bounds: CircuitBounds,
  viewport: ViewportSize,
  padding: number = 40,
): Transform {
  const worldWidth = bounds.max_x - bounds.min_x;
  const worldHeight = bounds.max_y - bounds.min_y;

  const availableWidth = viewport.width - padding * 2;
  const availableHeight = viewport.height - padding * 2;

  const scaleX = availableWidth / worldWidth;
  const scaleY = availableHeight / worldHeight;
  const scale = Math.min(scaleX, scaleY);

  const scaledWidth = worldWidth * scale;
  const scaledHeight = worldHeight * scale;
  const offsetX = (viewport.width - scaledWidth) / 2 - bounds.min_x * scale;
  // Flip Y: screen Y increases downward, world Y increases upward
  const offsetY = (viewport.height - scaledHeight) / 2 + bounds.max_y * scale;

  return { scale, offsetX, offsetY };
}

/**
 * Convert a world coordinate to screen pixel coordinate.
 */
export function worldToScreen(
  worldX: number,
  worldY: number,
  transform: Transform,
): { screenX: number; screenY: number } {
  return {
    screenX: worldX * transform.scale + transform.offsetX,
    screenY: -worldY * transform.scale + transform.offsetY,
  };
}

/**
 * Convert screen pixel coordinate back to world coordinate.
 */
export function screenToWorld(
  screenX: number,
  screenY: number,
  transform: Transform,
): { worldX: number; worldY: number } {
  return {
    worldX: (screenX - transform.offsetX) / transform.scale,
    worldY: -(screenY - transform.offsetY) / transform.scale,
  };
}
