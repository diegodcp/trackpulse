/**
 * chunkConverter.worker.ts — offloads chunkToFrames() conversion off the main thread.
 *
 * The main thread sends a compact chunk and receives back the converted TimelineFrame[].
 * This eliminates main-thread jank when processing large chunks.
 */

interface DriverMeta {
  driver_number: number;
  name_acronym: string;
  team_colour: string;
}

interface DriverPositions {
  x: (number | null)[];
  y: (number | null)[];
  speed: (number | null)[];
  position: (number | null)[];
  lap: (number | null)[];
}

interface CompactChunk {
  session_key: number;
  total_duration_seconds: number;
  target_hz: number;
  total_chunks: number;
  chunk_index: number;
  chunk_start_seconds: number;
  chunk_end_seconds: number;
  frame_count: number;
  drivers: DriverMeta[];
  elapsed: number[];
  positions: Record<string, DriverPositions>;
}

interface CarFrame {
  driver_number: number;
  x: number;
  y: number;
  speed: number | null;
  position: number | null;
  lap_number: number | null;
  name_acronym: string;
  team_colour: string;
}

interface TimelineFrame {
  timestamp: string;
  elapsed_seconds: number;
  cars: CarFrame[];
}

export type ChunkConverterRequest = {
  type: 'convert';
  id: number;
  chunk: CompactChunk;
};

export type ChunkConverterResponse = {
  type: 'converted';
  id: number;
  frames: TimelineFrame[];
};

/**
 * Convert a compact columnar chunk into TimelineFrame[] row format.
 */
function chunkToFrames(chunk: CompactChunk): TimelineFrame[] {
  const frames: TimelineFrame[] = [];
  const { drivers, elapsed, positions } = chunk;

  for (let i = 0; i < elapsed.length; i++) {
    const cars: CarFrame[] = [];
    for (const driver of drivers) {
      const driverPos = positions[String(driver.driver_number)];
      if (!driverPos) continue;

      const x = driverPos.x[i];
      const y = driverPos.y[i];

      cars.push({
        driver_number: driver.driver_number,
        x: x ?? NaN,
        y: y ?? NaN,
        speed: driverPos.speed[i],
        position: driverPos.position[i],
        lap_number: driverPos.lap[i],
        name_acronym: driver.name_acronym,
        team_colour: driver.team_colour,
      });
    }

    frames.push({
      timestamp: '',
      elapsed_seconds: elapsed[i],
      cars,
    });
  }

  return frames;
}

self.onmessage = (e: MessageEvent<ChunkConverterRequest>) => {
  const { type, id, chunk } = e.data;

  if (type === 'convert') {
    const frames = chunkToFrames(chunk);
    const response: ChunkConverterResponse = { type: 'converted', id, frames };
    self.postMessage(response);
  }
};
