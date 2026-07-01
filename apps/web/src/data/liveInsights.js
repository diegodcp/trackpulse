import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';

const insightEvidenceValueSchema = z.object({
  value: z.unknown(),
  truth_label: z.string().optional()
});

const liveInsightSchema = z.object({
  insight_id: z.string(),
  severity: z.string(),
  title: z.string(),
  message: z.string(),
  confidence: z.coerce.number().min(0).max(1),
  truth_labels: z.array(z.string()).default([]),
  evidence: z.record(insightEvidenceValueSchema).default({})
});

const latestInsightsSchema = z
  .object({
    insights: z.array(liveInsightSchema)
  })
  .passthrough();

const trackSnapshotFallbackSchema = z
  .object({
    snapshot: z
      .object({
        live_insights: z.array(liveInsightSchema).default([])
      })
      .passthrough()
  })
  .passthrough();

function titleCase(value) {
  const normalized = String(value ?? '').trim().toLowerCase();
  if (!normalized) {
    return 'Unknown';
  }
  return normalized[0].toUpperCase() + normalized.slice(1);
}

function formatEvidenceValue(value) {
  if (value == null) {
    return 'n/a';
  }
  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : value.toFixed(1);
  }
  if (typeof value === 'boolean') {
    return value ? 'yes' : 'no';
  }
  return String(value);
}

function normalizeInsight(insight) {
  const evidence = Object.entries(insight.evidence).map(([key, raw]) => ({
    key,
    value: formatEvidenceValue(raw.value),
    truthLabel: titleCase(raw.truth_label)
  }));

  return {
    id: insight.insight_id,
    severity: titleCase(insight.severity),
    title: insight.title,
    message: insight.message,
    confidence: insight.confidence,
    truthLabels: insight.truth_labels.map(titleCase),
    evidence
  };
}

async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Failed to fetch ${path}`);
  }
  return response.json();
}

async function fetchLiveInsights() {
  try {
    const payload = await fetchJson('/api/v1/insights/latest');
    return latestInsightsSchema.parse(payload).insights.map(normalizeInsight);
  } catch {
    const fallbackPayload = await fetchJson('/api/v1/track-state/latest');
    return trackSnapshotFallbackSchema.parse(fallbackPayload).snapshot.live_insights.map(normalizeInsight);
  }
}

export function useLiveInsights() {
  return useQuery({
    queryKey: ['live-insights', 'latest'],
    queryFn: fetchLiveInsights,
    staleTime: 2_000,
    retry: false,
    refetchInterval: 2_000
  });
}
