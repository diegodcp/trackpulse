import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import { meetingsResponseSchema, Meeting } from '../types/session';

export function useSessions(year: number | null) {
  return useQuery<Meeting[]>({
    queryKey: ['sessions', year],
    queryFn: async () => {
      const data = await apiFetch(`/api/v1/sessions?year=${year}`);
      return meetingsResponseSchema.parse(data);
    },
    enabled: year !== null,
  });
}
