import { z } from 'zod';

const replayPointSchema = z.object({
  occurred_at: z.string(),
  driver_number: z.coerce.number(),
  x: z.coerce.number(),
  y: z.coerce.number()
});

const replayBoundsSchema = z
  .object({
    min_x: z.coerce.number(),
    max_x: z.coerce.number(),
    min_y: z.coerce.number(),
    max_y: z.coerce.number()
  })
  .nullable()
  .optional();

const replayStateSchema = z.object({
  fixture_id: z.string(),
  status: z.string(),
  speed_multiplier: z.coerce.number(),
  cursor: z.coerce.number(),
  total_points: z.coerce.number(),
  progress_pct: z.coerce.number(),
  replay_time: z.string().nullable().optional(),
  active_location: replayPointSchema.nullable().optional(),
  coordinate_bounds: replayBoundsSchema,
  timeline_points: z.array(replayPointSchema).default([])
});

const replayFixturesSchema = z.object({
  fixtures: z.array(
    z.object({
      fixture_id: z.string(),
      display_name: z.string(),
      source_mode: z.string(),
      supported_speeds: z.array(z.coerce.number())
    })
  )
});

async function decodeJson(response, errorLabel) {
  if (!response.ok) {
    throw new Error(errorLabel);
  }
  return response.json();
}

export async function fetchReplayFixtures() {
  const response = await fetch('/api/v1/replay/fixtures');
  const payload = await decodeJson(response, 'Failed to fetch replay fixtures');
  return replayFixturesSchema.parse(payload).fixtures;
}

export async function fetchReplayState() {
  const response = await fetch('/api/v1/replay/state');
  const payload = await decodeJson(response, 'Failed to fetch replay state');
  return replayStateSchema.parse(payload);
}

export async function startReplay({ fixtureId, speedMultiplier }) {
  const response = await fetch('/api/v1/replay/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fixture_id: fixtureId, speed_multiplier: speedMultiplier })
  });
  const payload = await decodeJson(response, 'Failed to start replay');
  return replayStateSchema.parse(payload);
}

export async function stopReplay() {
  const response = await fetch('/api/v1/replay/stop', {
    method: 'POST'
  });
  const payload = await decodeJson(response, 'Failed to stop replay');
  return replayStateSchema.parse(payload);
}

const replayStatusSchema = z.object({
  fixture_id: z.string(),
  status: z.string(),
  speed_multiplier: z.coerce.number(),
  cursor: z.coerce.number(),
  total_points: z.coerce.number(),
  progress_pct: z.coerce.number(),
  replay_time: z.string().nullable().optional(),
  message: z.string().optional()
});

export async function fetchReplayStatus() {
  const response = await fetch('/api/v1/events/replay-status');
  const payload = await decodeJson(response, 'Failed to fetch replay status');
  return replayStatusSchema.parse(payload);
}

export async function startFixtureReplay(fixtureId, speedMultiplier) {
  const response = await fetch(`/api/v1/replay/${encodeURIComponent(fixtureId)}/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ speed_multiplier: speedMultiplier })
  });
  const payload = await decodeJson(response, 'Failed to start replay');
  return replayStatusSchema.parse(payload);
}

export async function pauseFixtureReplay(fixtureId) {
  const response = await fetch(`/api/v1/replay/${encodeURIComponent(fixtureId)}/pause`, {
    method: 'POST'
  });
  const payload = await decodeJson(response, 'Failed to pause replay');
  return replayStatusSchema.parse(payload);
}

export async function stopFixtureReplay(fixtureId) {
  const response = await fetch(`/api/v1/replay/${encodeURIComponent(fixtureId)}/stop`, {
    method: 'POST'
  });
  const payload = await decodeJson(response, 'Failed to stop replay');
  return replayStatusSchema.parse(payload);
}
