import { useCallback, useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import {
  compactChunkSchema,
  type CompactChunk,
  type DriverMeta,
  type TimelineFrame,
  type CarFrame,
} from '../types/timeline';

const DEFAULT_HZ = 2;
const DEFAULT_CHUNK_SECONDS = 120;
const PREFETCH_AHEAD = 1; // prefetch N chunks ahead

interface ChunkedTimeline {
  durationSeconds: number;
  targetHz: number;
  totalChunks: number;
  drivers: DriverMeta[];
  getFramesForTime: (elapsedSeconds: number) => {
    frames: TimelineFrame[];
    chunkStart: number;
  } | null;
  isReady: boolean;
  isLoading: boolean;
}

/**
 * Converts a compact chunk to the TimelineFrame[] format used by interpolation.
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

      // Include car even if null (will be filtered by interpolation as NaN)
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

function chunkQueryKey(
  sessionKey: number,
  chunkIndex: number,
  hz: number,
  chunkSeconds: number,
) {
  return ['carTimelineChunk', sessionKey, chunkIndex, hz, chunkSeconds] as const;
}

export function useCarTimeline(
  sessionKey: number | null,
  hz: number = DEFAULT_HZ,
  chunkSeconds: number = DEFAULT_CHUNK_SECONDS,
): ChunkedTimeline {
  const queryClient = useQueryClient();
  const chunksRef = useRef<Map<number, TimelineFrame[]>>(new Map());
  const [isReady, setIsReady] = useState(false);
  const metaRef = useRef<{
    durationSeconds: number;
    totalChunks: number;
    drivers: DriverMeta[];
  } | null>(null);

  // Fetch first chunk to get metadata
  const { data: firstChunk, isLoading } = useQuery<CompactChunk>({
    queryKey: chunkQueryKey(sessionKey!, 0, hz, chunkSeconds),
    queryFn: async () => {
      const data = await apiFetch(
        `/api/v1/sessions/${sessionKey}/timeline/cars/compact?hz=${hz}&chunk=0&chunk_seconds=${chunkSeconds}`,
      );
      return compactChunkSchema.parse(data);
    },
    enabled: sessionKey !== null,
    staleTime: Infinity,
  });

  // Process first chunk and store metadata
  useEffect(() => {
    if (!firstChunk) return;
    metaRef.current = {
      durationSeconds: firstChunk.total_duration_seconds,
      totalChunks: firstChunk.total_chunks,
      drivers: firstChunk.drivers,
    };
    chunksRef.current.set(0, chunkToFrames(firstChunk));
    setIsReady(true);
  }, [firstChunk]);

  // Reset when session changes
  useEffect(() => {
    chunksRef.current.clear();
    metaRef.current = null;
    setIsReady(false);
  }, [sessionKey]);

  // Prefetch a chunk
  const prefetchChunk = useCallback(
    (chunkIndex: number) => {
      if (sessionKey === null) return;
      const meta = metaRef.current;
      if (!meta || chunkIndex >= meta.totalChunks || chunkIndex < 0) return;
      if (chunksRef.current.has(chunkIndex)) return;

      queryClient.prefetchQuery({
        queryKey: chunkQueryKey(sessionKey, chunkIndex, hz, chunkSeconds),
        queryFn: async () => {
          const data = await apiFetch(
            `/api/v1/sessions/${sessionKey}/timeline/cars/compact?hz=${hz}&chunk=${chunkIndex}&chunk_seconds=${chunkSeconds}`,
          );
          const chunk = compactChunkSchema.parse(data);
          chunksRef.current.set(chunkIndex, chunkToFrames(chunk));
          return chunk;
        },
        staleTime: Infinity,
      });
    },
    [sessionKey, hz, chunkSeconds, queryClient],
  );

  const getFramesForTime = useCallback(
    (elapsedSeconds: number) => {
      const meta = metaRef.current;
      if (!meta) return null;

      const chunkIndex = Math.min(
        Math.floor(elapsedSeconds / chunkSeconds),
        meta.totalChunks - 1,
      );

      // Prefetch upcoming chunks
      for (let i = 1; i <= PREFETCH_AHEAD; i++) {
        prefetchChunk(chunkIndex + i);
      }

      const frames = chunksRef.current.get(chunkIndex);
      if (!frames) {
        // Chunk not loaded yet — trigger fetch
        prefetchChunk(chunkIndex);
        return null;
      }

      return {
        frames,
        chunkStart: chunkIndex * chunkSeconds,
      };
    },
    [chunkSeconds, prefetchChunk],
  );

  return {
    durationSeconds: metaRef.current?.durationSeconds ?? 0,
    targetHz: hz,
    totalChunks: metaRef.current?.totalChunks ?? 0,
    drivers: metaRef.current?.drivers ?? [],
    getFramesForTime,
    isReady,
    isLoading,
  };
}
