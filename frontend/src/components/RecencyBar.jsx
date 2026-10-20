import './RecencyBar.css';

export default function RecencyBar({ weight, signal }) {
  const pct = Math.max(0, Math.min(100, weight));
  const colorVar = signal === 'bullish' ? 'var(--color-bullish-strong)' : 'var(--color-bearish-strong)';
  return (
    <div className="recency" title={`Recency weight: ${pct}`}>
      <div className="recency__track">
        <div className="recency__fill" style={{ width: `${pct}%`, background: colorVar }} />
      </div>
      <span className="recency__value num">{pct}</span>
    </div>
  );
}
