import { z } from 'zod';

export const pointSchema = z.object({
  x: z.number(),
  y: z.number(),
  cumulative_dist: z.number(),
});

export const segmentSchema = z.object({
  id: z.number(),
  start_idx: z.number(),
  end_idx: z.number(),
  sector: z.number(),
  start_dist: z.number(),
  end_dist: z.number(),
});

export const boundsSchema = z.object({
  min_x: z.number(),
  max_x: z.number(),
  min_y: z.number(),
  max_y: z.number(),
});

export const circuitGeometrySchema = z.object({
  session_key: z.number(),
  total_points: z.number(),
  total_length: z.number(),
  bounds: boundsSchema,
  points: z.array(pointSchema),
  segments: z.array(segmentSchema),
  source_driver: z.number().nullable(),
  source_lap: z.number().nullable(),
});

export type CircuitPoint = z.infer<typeof pointSchema>;
export type CircuitSegment = z.infer<typeof segmentSchema>;
export type CircuitBounds = z.infer<typeof boundsSchema>;
export type CircuitGeometry = z.infer<typeof circuitGeometrySchema>;
