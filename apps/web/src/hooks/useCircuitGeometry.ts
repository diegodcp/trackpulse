import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import { circuitGeometrySchema, type CircuitGeometry } from '../types/circuit';

export function useCircuitGeometry(sessionKey: number | null) {
  return useQuery<CircuitGeometry>({
    queryKey: ['circuit', sessionKey],
    queryFn: async () => {
      const data = await apiFetch(`/api/v1/sessions/${sessionKey}/circuit`);
      return circuitGeometrySchema.parse(data);
    },
    enabled: sessionKey !== null,
    staleTime: Infinity,
  });
}
