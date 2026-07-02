import { z } from 'zod';

export const sessionInfoSchema = z.object({
  session_key: z.number(),
  session_name: z.string(),
  session_type: z.string(),
  date_start: z.string(),
  date_end: z.string().nullable(),
});

export const meetingSchema = z.object({
  meeting_key: z.number(),
  meeting_name: z.string(),
  country_name: z.string(),
  location: z.string(),
  circuit_short_name: z.string(),
  year: z.number(),
  date_start: z.string(),
  sessions: z.array(sessionInfoSchema),
});

export const meetingsResponseSchema = z.array(meetingSchema);

export type SessionInfo = z.infer<typeof sessionInfoSchema>;
export type Meeting = z.infer<typeof meetingSchema>;
