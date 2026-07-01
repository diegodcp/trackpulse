import { InsightCard } from './InsightCard';

export function InsightPanel({ query }) {
  const insights = query.data ?? [];

  return (
    <section className="insight-panel" aria-label="Insights">
      <h2>Live Insights</h2>
      {query.isLoading ? <p className="insight-panel-state">Loading live insights...</p> : null}
      {query.isError ? <p className="insight-panel-state">Live insights are temporarily unavailable.</p> : null}
      {!query.isLoading && !query.isError && insights.length === 0 ? (
        <p className="insight-panel-state">No active insights right now. Start replay to populate this panel.</p>
      ) : null}
      <div className="insight-grid">
        {insights.map((insight) => (
          <InsightCard
            key={insight.id}
            severity={insight.severity}
            title={insight.title}
            message={insight.message}
            confidence={insight.confidence}
            truthLabels={insight.truthLabels}
            evidence={insight.evidence}
          />
        ))}
      </div>
    </section>
  );
}
