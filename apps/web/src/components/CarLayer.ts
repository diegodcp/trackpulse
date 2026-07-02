import { useEffect, useRef } from 'react';
import type { Application } from 'pixi.js';
import type { InterpolatedCar } from '../utils/interpolation';
import { CarMarkerSprite } from './CarMarker';
import { worldToScreen, type Transform } from '../utils/coordinates';

interface CarLayerProps {
  app: Application | null;
  cars: InterpolatedCar[];
  transform: Transform | null;
}

export function useCarLayer({ app, cars, transform }: CarLayerProps) {
  const markersRef = useRef<Map<number, CarMarkerSprite>>(new Map());

  useEffect(() => {
    if (!app || !transform || cars.length === 0) return;

    const currentDrivers = new Set<number>();

    for (const car of cars) {
      currentDrivers.add(car.driver_number);
      let marker = markersRef.current.get(car.driver_number);

      if (!marker) {
        marker = new CarMarkerSprite(car.team_colour, car.name_acronym);
        app.stage.addChild(marker.container);
        markersRef.current.set(car.driver_number, marker);
      }

      const { screenX, screenY } = worldToScreen(car.x, car.y, transform);
      marker.updatePosition(screenX, screenY);

      if (car.inPit) {
        marker.setInPit(true);
      } else {
        marker.setActive(car.isActive);
      }
    }

    // Remove markers for drivers no longer present
    for (const [driverNum, marker] of markersRef.current) {
      if (!currentDrivers.has(driverNum)) {
        marker.destroy();
        markersRef.current.delete(driverNum);
      }
    }
  }, [app, cars, transform]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      for (const marker of markersRef.current.values()) {
        marker.destroy();
      }
      markersRef.current.clear();
    };
  }, []);
}
