import './SignalFilterBar.css';

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'bullish', label: 'Bullish' },
  { id: 'bearish', label: 'Bearish' },
];

export default function SignalFilterBar({ counts, active, onChange }) {
  return (
    <div className="filter-bar" role="group" aria-label="Filter signals">
      {FILTERS.map((f) => (
        <button
          key={f.id}
          type="button"
          className={'filter-pill' + (active === f.id ? ' filter-pill--active' : '')}
          aria-pressed={active === f.id}
          onClick={() => onChange(f.id)}
        >
          {f.label} <span className="filter-pill__count num">{counts[f.id] ?? 0}</span>
        </button>
      ))}
    </div>
  );
}
