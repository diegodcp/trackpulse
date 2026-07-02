import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useCarLayer } from '../src/components/CarLayer';
import type { InterpolatedCar } from '../src/utils/interpolation';

// Mock pixi.js Container
vi.mock('pixi.js', () => ({
  Graphics: vi.fn().mockImplementation(() => ({
    circle: vi.fn().mockReturnThis(),
    fill: vi.fn().mockReturnThis(),
  })),
  Text: vi.fn().mockImplementation(() => ({
    anchor: { set: vi.fn() },
    y: 0,
  })),
  Container: vi.fn().mockImplementation(() => ({
    addChild: vi.fn(),
    removeChild: vi.fn(),
    destroy: vi.fn(),
    x: 0,
    y: 0,
    alpha: 1,
  })),
}));

function makeCar(overrides: Partial<InterpolatedCar> = {}): InterpolatedCar {
  return {
    driver_number: 1,
    x: 100,
    y: 200,
    speed: 300,
    position: 1,
    lap_number: 5,
    name_acronym: 'VER',
    team_colour: '3671C6',
    isActive: true,
    inPit: false,
    ...overrides,
  };
}

function makeApp() {
  return {
    stage: {
      addChild: vi.fn(),
      removeChild: vi.fn(),
    },
    ticker: { add: vi.fn(), remove: vi.fn() },
    screen: { width: 800, height: 600 },
  } as any;
}

const mockTransform = { scale: 1, offsetX: 0, offsetY: 0 };

describe('useCarLayer', () => {
  it('does nothing when app is null', () => {
    const { result } = renderHook(() =>
      useCarLayer({ app: null, cars: [makeCar()], transform: mockTransform }),
    );
    // Should not throw
    expect(result.current).toBeUndefined();
  });

  it('does nothing when transform is null', () => {
    const app = makeApp();
    const { result } = renderHook(() =>
      useCarLayer({ app, cars: [makeCar()], transform: null }),
    );
    expect(result.current).toBeUndefined();
  });

  it('does nothing when cars array is empty', () => {
    const app = makeApp();
    const { result } = renderHook(() =>
      useCarLayer({ app, cars: [], transform: mockTransform }),
    );
    expect(result.current).toBeUndefined();
  });

  it('creates markers when cars are provided', () => {
    const app = makeApp();
    const cars = [makeCar({ driver_number: 1 }), makeCar({ driver_number: 44 })];

    renderHook(() =>
      useCarLayer({ app, cars, transform: mockTransform }),
    );

    // Should add containers to stage
    expect(app.stage.addChild).toHaveBeenCalled();
  });
});
