import { TruthLabelBadge } from './TruthLabelBadge';

export function InsightCard({ severity, title, message, confidence, truthLabels, evidence }) {
  const confidencePercent = `${Math.round(confidence * 100)}%`;

  return (
    <article className="insight-card">
      <header className="insight-card-header">
        <h3>{title}</h3>
        <span className={`insight-severity insight-severity-${String(severity ?? '').toLowerCase()}`}>{severity}</span>
      </header>
      <p>{message}</p>
      <p className="insight-meta">Confidence: {confidencePercent}</p>
      <div className="insight-truth-labels" aria-label="Insight truth labels">
        {(truthLabels ?? []).map((label) => (
          <TruthLabelBadge key={label} label={label} />
        ))}
      </div>
      {Array.isArray(evidence) && evidence.length > 0 ? (
        <ul className="insight-evidence" aria-label="Insight evidence">
          {evidence.slice(0, 3).map((item) => (
            <li key={item.key}>
              <strong>{item.key.replaceAll('_', ' ')}:</strong> {item.value}
              {item.truthLabel ? ` (${item.truthLabel})` : ''}
            </li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}
