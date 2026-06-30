import { TruthLabelBadge } from './TruthLabelBadge';

export function InsightCard({ title, message, confidence, truthLabel }) {
  const confidencePercent = `${Math.round(confidence * 100)}%`;

  return (
    <article className="insight-card">
      <header className="insight-card-header">
        <h3>{title}</h3>
        <TruthLabelBadge label={truthLabel} />
      </header>
      <p>{message}</p>
      <p className="insight-meta">Confidence: {confidencePercent}</p>
    </article>
  );
}
