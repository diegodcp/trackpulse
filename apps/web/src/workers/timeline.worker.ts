/**
 * Timeline Web Worker — runs in a background thread.
 *
 * Responsibilities:
 * - Manages WebSocket connection to the streaming endpoint
 * - Buffers incoming frames in a ring buffer
 * - Interpolates car positions between buffered frames
 * - Posts interpolated car positions to the main thread on each tick
 *
 * The main thread's Pixi ticker only reads the latest positions from a ref,
 * doing ZERO computation — just position assignment.
 */

import { RingBuffer } from './ringBuffer';
import type {
  CompactCar,
  InterpolatedCar,
  MainToWorkerMessage,
  StreamFrame,
} from './types';

interface WorkerState {
  ws: WebSocket | null;
  frameBuffer: RingBuffer<StreamFrame>;
  sessionKey: number | null;
}

const state: WorkerState = {
  ws: null,
  frameBuffer: new RingBuffer<StreamFrame>(120), // ~30 seconds of frames at 4Hz
  sessionKey: null,
};

// --- Message handler from main thread ---

self.onmessage = (e: MessageEvent<MainToWorkerMessage>) => {
  const msg = e.data;

  switch (msg.type) {
    case 'connect':
      connectWebSocket(msg.payload.sessionKey, msg.payload.hz, msg.payload.speed);
      break;
    case 'seek':
      if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify({ cmd: 'seek', to: msg.payload.elapsed }));
      }
      state.frameBuffer.clear();
      break;
    case 'speed':
      if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify({ cmd: 'speed', value: msg.payload.value }));
      }
      break;
    case 'pause':
      if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify({ cmd: 'pause' }));
      }
      break;
    case 'resume':
      if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify({ cmd: 'resume' }));
      }
      break;
    case 'disconnect':
      disconnect();
      break;
  }
};

// --- WebSocket connection ---

function connectWebSocket(sessionKey: number, hz: number, speed: number): void {
  // Close existing connection if any
  disconnect();

  state.sessionKey = sessionKey;
  state.frameBuffer.clear();

  const protocol = self.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${self.location.host}/api/v1/sessions/${sessionKey}/timeline/cars/stream?hz=${hz}&speed=${speed}`;

  state.ws = new WebSocket(wsUrl);

  state.ws.onopen = () => {
    self.postMessage({ type: 'connected' });
  };

  state.ws.onmessage = (event: MessageEvent) => {
    const msg = JSON.parse(event.data as string);

    if (msg.type === 'frame') {
      const frame = msg as StreamFrame;
      state.frameBuffer.push(frame);

      // Interpolate at current elapsed and send to main thread
      const cars = frameToCarArray(frame);
      self.postMessage({ type: 'tick', elapsed: frame.elapsed, cars, weather: frame.weather });
    } else if (msg.type === 'end') {
      self.postMessage({ type: 'end' });
    } else if (msg.type === 'error') {
      self.postMessage({ type: 'error', detail: msg.detail || 'Unknown error' });
    }
  };

  state.ws.onclose = () => {
    self.postMessage({ type: 'disconnected' });
  };

  state.ws.onerror = () => {
    self.postMessage({ type: 'error', detail: 'WebSocket connection error' });
  };
}

function disconnect(): void {
  if (state.ws) {
    state.ws.close();
    state.ws = null;
  }
  state.sessionKey = null;
}

// --- Frame conversion ---

/**
 * Convert a compact stream frame to an array of InterpolatedCar objects.
 * This is the "current frame" — no interpolation needed since the server
 * already sends at the exact playback Hz.
 */
function frameToCarArray(frame: StreamFrame): InterpolatedCar[] {
  const cars: InterpolatedCar[] = [];

  for (const [driverStr, data] of Object.entries(frame.cars)) {
    cars.push(compactToInterpolated(parseInt(driverStr, 10), data));
  }

  return cars;
}

function compactToInterpolated(driverNumber: number, car: CompactCar): InterpolatedCar {
  return {
    driver_number: driverNumber,
    x: car.x,
    y: car.y,
    speed: car.s,
    position: car.p,
    lap_number: car.l,
    isActive: true,
  };
}

/**
 * Interpolate between two frames at a given factor t ∈ [0, 1].
 * Used when the main thread requests a position between two buffered frames.
 */
export function lerpFrames(
  before: StreamFrame,
  after: StreamFrame,
  t: number,
): InterpolatedCar[] {
  const allDrivers = new Set([
    ...Object.keys(before.cars),
    ...Object.keys(after.cars),
  ]);

  const cars: InterpolatedCar[] = [];

  for (const driverStr of allDrivers) {
    const b = before.cars[driverStr];
    const a = after.cars[driverStr];
    const dn = parseInt(driverStr, 10);

    if (b && a) {
      cars.push({
        driver_number: dn,
        x: b.x + (a.x - b.x) * t,
        y: b.y + (a.y - b.y) * t,
        speed: b.s, // forward-fill discrete values
        position: b.p,
        lap_number: b.l,
        isActive: true,
      });
    } else if (b) {
      cars.push(compactToInterpolated(dn, b));
    } else if (a) {
      cars.push(compactToInterpolated(dn, a));
    }
  }

  return cars;
}
