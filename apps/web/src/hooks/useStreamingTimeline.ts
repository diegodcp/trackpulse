import { useRef, useEffect, useCallback, useState } from 'react';
import type { InterpolatedCar, MainToWorkerMessage, StreamWeather, WorkerToMainMessage } from '../workers/types';

export interface UseStreamingTimelineOptions {
  sessionKey: number | null;
  hz?: number;
  speed?: number;
  enabled?: boolean;
}

export interface StreamingTimeline {
  /** Latest elapsed time received from server */
  currentElapsed: React.RefObject<number>;
  /** Latest interpolated car positions (updated by worker, read by ticker) */
  carsRef: React.RefObject<InterpolatedCar[]>;
  /** Latest weather state (updated by worker) */
  weatherRef: React.RefObject<StreamWeather | null>;
  /** Control methods */
  seek: (elapsed: number) => void;
  setSpeed: (speed: number) => void;
  pause: () => void;
  resume: () => void;
  disconnect: () => void;
  /** Connection state */
  isConnected: boolean;
  isEnded: boolean;
}

export function useStreamingTimeline({
  sessionKey,
  hz = 4,
  speed = 1,
  enabled = true,
}: UseStreamingTimelineOptions): StreamingTimeline {
  const workerRef = useRef<Worker | null>(null);
  const currentElapsed = useRef(0);
  const carsRef = useRef<InterpolatedCar[]>([]);
  const weatherRef = useRef<StreamWeather | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isEnded, setIsEnded] = useState(false);

  useEffect(() => {
    if (!sessionKey || !enabled) return;

    const worker = new Worker(
      new URL('../workers/timeline.worker.ts', import.meta.url),
      { type: 'module' },
    );
    workerRef.current = worker;

    worker.onmessage = (e: MessageEvent<WorkerToMainMessage>) => {
      const msg = e.data;

      switch (msg.type) {
        case 'tick':
          currentElapsed.current = msg.elapsed;
          carsRef.current = msg.cars;
          weatherRef.current = msg.weather ?? null;
          break;
        case 'connected':
          setIsConnected(true);
          break;
        case 'end':
          setIsEnded(true);
          break;
        case 'disconnected':
          setIsConnected(false);
          break;
        case 'error':
          // Could expose via state if needed
          console.warn('[StreamingTimeline] Worker error:', msg.detail);
          break;
      }
    };

    // Connect to the WebSocket via the worker
    const connectMsg: MainToWorkerMessage = {
      type: 'connect',
      payload: { sessionKey, hz, speed },
    };
    worker.postMessage(connectMsg);
    setIsEnded(false);

    return () => {
      const disconnectMsg: MainToWorkerMessage = { type: 'disconnect' };
      worker.postMessage(disconnectMsg);
      worker.terminate();
      workerRef.current = null;
      setIsConnected(false);
    };
  }, [sessionKey, hz, speed, enabled]);

  const seek = useCallback((elapsed: number) => {
    const msg: MainToWorkerMessage = { type: 'seek', payload: { elapsed } };
    workerRef.current?.postMessage(msg);
    currentElapsed.current = elapsed;
  }, []);

  const setSpeed = useCallback((value: number) => {
    const msg: MainToWorkerMessage = { type: 'speed', payload: { value } };
    workerRef.current?.postMessage(msg);
  }, []);

  const pause = useCallback(() => {
    const msg: MainToWorkerMessage = { type: 'pause' };
    workerRef.current?.postMessage(msg);
  }, []);

  const resume = useCallback(() => {
    const msg: MainToWorkerMessage = { type: 'resume' };
    workerRef.current?.postMessage(msg);
  }, []);

  const disconnect = useCallback(() => {
    const msg: MainToWorkerMessage = { type: 'disconnect' };
    workerRef.current?.postMessage(msg);
  }, []);

  return {
    currentElapsed,
    carsRef,
    weatherRef,
    seek,
    setSpeed,
    pause,
    resume,
    disconnect,
    isConnected,
    isEnded,
  };
}
