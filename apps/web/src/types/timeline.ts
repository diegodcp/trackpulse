import { z } from 'zod';

export const carFrameSchema = z.object({
  driver_number: z.number(),
  x: z.number(),
  y: z.number(),
  speed: z.number().nullable(),
  position: z.number().nullable(),
  lap_number: z.number().nullable(),
  name_acronym: z.string(),
  team_colour: z.string(),
});

export const timelineFrameSchema = z.object({
  timestamp: z.string(),
  elapsed_seconds: z.number(),
  cars: z.array(carFrameSchema),
  weather: z
    .object({
      air_temperature: z.number(),
      track_temperature: z.number(),
      humidity: z.number(),
      wind_speed: z.number(),
      wind_direction: z.number(),
      rainfall: z.boolean(),
    })
    .nullable()
    .optional(),
});

export const carTimelineSchema = z.object({
  session_key: z.number(),
  total_frames: z.number(),
  duration_seconds: z.number(),
  target_hz: z.number(),
  frames: z.array(timelineFrameSchema),
});

export type CarFrame = z.infer<typeof carFrameSchema>;
export type TimelineFrame = z.infer<typeof timelineFrameSchema>;
export type CarTimeline = z.infer<typeof carTimelineSchema>;

// --- Compact chunked format ---

export const driverMetaSchema = z.object({
  driver_number: z.number(),
  name_acronym: z.string(),
  team_colour: z.string(),
});

export const driverPositionsSchema = z.object({
  x: z.array(z.number().nullable()),
  y: z.array(z.number().nullable()),
  speed: z.array(z.number().nullable()),
  position: z.array(z.number().nullable()),
  lap: z.array(z.number().nullable()),
});

export const compactChunkSchema = z.object({
  session_key: z.number(),
  total_duration_seconds: z.number(),
  target_hz: z.number(),
  total_chunks: z.number(),
  chunk_index: z.number(),
  chunk_start_seconds: z.number(),
  chunk_end_seconds: z.number(),
  frame_count: z.number(),
  drivers: z.array(driverMetaSchema),
  elapsed: z.array(z.number()),
  positions: z.record(z.string(), driverPositionsSchema),
  weather: z
    .array(
      z.object({
        air_temperature: z.number(),
        track_temperature: z.number(),
        humidity: z.number(),
        wind_speed: z.number(),
        wind_direction: z.number(),
        rainfall: z.boolean(),
      }),
    )
    .nullable()
    .optional(),
  race_start_elapsed_seconds: z.number().nullable().optional(),
});

export type DriverMeta = z.infer<typeof driverMetaSchema>;
export type DriverPositions = z.infer<typeof driverPositionsSchema>;
export type CompactChunk = z.infer<typeof compactChunkSchema>;

// --- Weather state ---

export interface WeatherState {
  air_temperature: number;
  track_temperature: number;
  humidity: number;
  wind_speed: number;
  wind_direction: number;
  rainfall: boolean;
}
