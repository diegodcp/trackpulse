import { describe, it, expect } from 'vitest';
import { computeTransform, worldToScreen, screenToWorld } from '../src/utils/coordinates';

describe('computeTransform', () => {
  it('scales to fit viewport with padding', () => {
    const bounds = { min_x: 0, max_x: 1000, min_y: 0, max_y: 500 };
    const viewport = { width: 800, height: 600 };
    const transform = computeTransform(bounds, viewport, 40);

    // With 40px padding: available = 720x520
    // World is 1000x500 → scaleX=0.72, scaleY=1.04 → scale=0.72
    expect(transform.scale).toBeCloseTo(0.72, 1);
  });

  it('maintains aspect ratio', () => {
    const bounds = { min_x: 0, max_x: 100, min_y: 0, max_y: 100 };
    const viewport = { width: 800, height: 400 };
    const transform = computeTransform(bounds, viewport, 0);

    // Should use height as limiting factor (400/100 = 4)
    expect(transform.scale).toBeCloseTo(4, 1);
  });

  it('centers circuit in viewport', () => {
    const bounds = { min_x: 0, max_x: 100, min_y: 0, max_y: 100 };
    const viewport = { width: 400, height: 400 };
    const transform = computeTransform(bounds, viewport, 0);

    // world (0,100) = top-left on screen, world (100,0) = bottom-right on screen
    const topLeft = worldToScreen(0, 100, transform);
    const bottomRight = worldToScreen(100, 0, transform);
    const centerX = (topLeft.screenX + bottomRight.screenX) / 2;
    const centerY = (topLeft.screenY + bottomRight.screenY) / 2;
    expect(centerX).toBeCloseTo(200, 0);
    expect(centerY).toBeCloseTo(200, 0);
  });

  it('flips Y axis (higher world Y = lower screen Y)', () => {
    const bounds = { min_x: 0, max_x: 100, min_y: 0, max_y: 100 };
    const viewport = { width: 400, height: 400 };
    const transform = computeTransform(bounds, viewport, 0);

    const top = worldToScreen(50, 100, transform);
    const bottom = worldToScreen(50, 0, transform);
    expect(top.screenY).toBeLessThan(bottom.screenY);
  });

  it('handles negative bounds', () => {
    const bounds = { min_x: -500, max_x: 500, min_y: -300, max_y: 300 };
    const viewport = { width: 1000, height: 600 };
    const transform = computeTransform(bounds, viewport, 0);

    // World is 1000x600, viewport is 1000x600 → scale=1
    expect(transform.scale).toBeCloseTo(1, 1);
  });

  it('uses default padding of 40', () => {
    const bounds = { min_x: 0, max_x: 1000, min_y: 0, max_y: 1000 };
    const viewport = { width: 1080, height: 1080 };
    const transform = computeTransform(bounds, viewport);

    // Available = 1000x1000, world = 1000x1000 → scale=1
    expect(transform.scale).toBeCloseTo(1, 1);
  });
});

describe('worldToScreen', () => {
  it('converts world coordinates to screen with Y flipped', () => {
    const transform = { scale: 2, offsetX: 10, offsetY: 20 };
    const result = worldToScreen(5, 3, transform);
    expect(result.screenX).toBe(20); // 5*2 + 10
    expect(result.screenY).toBe(14); // -3*2 + 20
  });
});

describe('screenToWorld', () => {
  it('converts screen coordinates to world with Y flipped', () => {
    const transform = { scale: 2, offsetX: 10, offsetY: 20 };
    const result = screenToWorld(20, 14, transform);
    expect(result.worldX).toBe(5);
    expect(result.worldY).toBe(3);
  });
});

describe('worldToScreen / screenToWorld round-trip', () => {
  it('is reversible', () => {
    const bounds = { min_x: -500, max_x: 500, min_y: -300, max_y: 300 };
    const viewport = { width: 1200, height: 800 };
    const transform = computeTransform(bounds, viewport);

    const { screenX, screenY } = worldToScreen(100, -50, transform);
    const { worldX, worldY } = screenToWorld(screenX, screenY, transform);

    expect(worldX).toBeCloseTo(100, 5);
    expect(worldY).toBeCloseTo(-50, 5);
  });

  it('is reversible for edge coordinates', () => {
    const bounds = { min_x: 0, max_x: 1000, min_y: 0, max_y: 500 };
    const viewport = { width: 800, height: 600 };
    const transform = computeTransform(bounds, viewport, 40);

    const { screenX, screenY } = worldToScreen(0, 0, transform);
    const { worldX, worldY } = screenToWorld(screenX, screenY, transform);

    expect(worldX).toBeCloseTo(0, 5);
    expect(worldY).toBeCloseTo(0, 5);
  });
});
