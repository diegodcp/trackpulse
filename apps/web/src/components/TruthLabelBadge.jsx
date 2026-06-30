const VALID_LABELS = {
  measured: 'Measured',
  derived: 'Derived',
  inferred: 'Inferred'
};

export function TruthLabelBadge({ label }) {
  const normalizedLabel = String(label ?? '').toLowerCase();
  const displayLabel = VALID_LABELS[normalizedLabel] ?? 'Unknown';

  return (
    <span className={`truth-label truth-label-${normalizedLabel}`}>
      {displayLabel}
    </span>
  );
}
