import { InsightCard } from './InsightCard';

export function InsightPanel({ insights }) {
  return (
    <section className="insight-panel" aria-label="Insights">
      <h2>Live Insights</h2>
      <div className="insight-grid">
        {insights.map((insight) => (
          <InsightCard
            key={insight.id}
            title={insight.title}
            message={insight.message}
            confidence={insight.confidence}
            truthLabel={insight.truthLabel}
          />
        ))}
      </div>
    </section>
  );
}
