/**
 * Shared types for communication between the main thread and the timeline worker.
 */

/** Compact car data as received from the WebSocket (short keys for minimal payload). */
export interface CompactCar {
  x: number;
  y: number;
  s: number | null; // speed
  p: number | null; // position
  l: number | null; // lap_number
}

/** Weather state included in each WebSocket frame. */
export interface StreamWeather {
  air_temperature: number;
  track_temperature: number;
  humidity: number;
  wind_speed: number;
  wind_direction: number;
  rainfall: boolean;
}

/** Per-segment wind data included in WebSocket frames. */
export interface StreamSegmentWind {
  segment_id: number;
  wind_class: 'headwind' | 'tailwind' | 'crosswind_left' | 'crosswind_right';
  effective_speed: number;
  headwind_component: number;
  crosswind_component: number;
}

/** A single frame received from the WebSocket stream. */
export interface StreamFrame {
  type: 'frame';
  elapsed: number;
  cars: Record<string, CompactCar>;
  weather?: StreamWeather;
  segment_wind?: StreamSegmentWind[];
}

/** Interpolated car position ready for rendering. */
export interface InterpolatedCar {
  driver_number: number;
  x: number;
  y: number;
  speed: number | null;
  position: number | null;
  lap_number: number | null;
  isActive: boolean;
}

// --- Messages from Main Thread → Worker ---

export type MainToWorkerMessage =
  | { type: 'connect'; payload: { sessionKey: number; hz: number; speed: number } }
  | { type: 'seek'; payload: { elapsed: number } }
  | { type: 'speed'; payload: { value: number } }
  | { type: 'pause' }
  | { type: 'resume' }
  | { type: 'disconnect' };

// --- Messages from Worker → Main Thread ---

export type WorkerToMainMessage =
  | { type: 'tick'; elapsed: number; cars: InterpolatedCar[]; weather?: StreamWeather; segment_wind?: StreamSegmentWind[] }
  | { type: 'end' }
  | { type: 'connected' }
  | { type: 'disconnected' }
  | { type: 'error'; detail: string };
