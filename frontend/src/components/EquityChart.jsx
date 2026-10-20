import './EquityChart.css';

const WIDTH = 720;
const HEIGHT = 220;
const PAD_LEFT = 56;
const PAD_RIGHT = 16;
const PAD_TOP = 16;
const PAD_BOTTOM = 24;

function buildPath(values, xScale, yScale) {
  return values.map((v, i) => `${i === 0 ? 'M' : 'L'} ${xScale(i)} ${yScale(v)}`).join(' ');
}

function formatCurrency(v) {
  if (Math.abs(v) >= 100000) return `${(v / 100000).toFixed(1)}L`;
  if (Math.abs(v) >= 1000) return `${(v / 1000).toFixed(0)}k`;
  return v.toFixed(0);
}

function formatDate(iso) {
  return new Date(iso + 'T00:00:00').toLocaleDateString('en-IN', { month: 'short', year: '2-digit' });
}

export default function EquityChart({ strategy, buyHold }) {
  const n = strategy.length;
  if (n === 0) {
    return <p className="helper-text">No equity data to chart.</p>;
  }

  const strategyValues = strategy.map((p) => p.equity);
  const buyHoldValues = buyHold.map((p) => p.equity);
  const allValues = [...strategyValues, ...buyHoldValues];
  const min = Math.min(...allValues);
  const max = Math.max(...allValues);
  const range = max - min || 1;

  const innerWidth = WIDTH - PAD_LEFT - PAD_RIGHT;
  const innerHeight = HEIGHT - PAD_TOP - PAD_BOTTOM;

  const xScale = (i) => PAD_LEFT + (n === 1 ? innerWidth / 2 : (i / (n - 1)) * innerWidth);
  const yScale = (v) => PAD_TOP + innerHeight - ((v - min) / range) * innerHeight;

  return (
    <div className="equity-chart">
      <div className="equity-chart__legend">
        <span className="equity-chart__legend-item">
          <span className="equity-chart__swatch equity-chart__swatch--strategy" /> Strategy
        </span>
        <span className="equity-chart__legend-item">
          <span className="equity-chart__swatch equity-chart__swatch--benchmark" /> Buy &amp; hold
        </span>
      </div>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="equity-chart__svg"
        role="img"
        aria-label="Equity curve: strategy versus buy and hold"
      >
        <line x1={PAD_LEFT} y1={PAD_TOP} x2={PAD_LEFT} y2={HEIGHT - PAD_BOTTOM} stroke="var(--color-border)" />
        <line
          x1={PAD_LEFT}
          y1={HEIGHT - PAD_BOTTOM}
          x2={WIDTH - PAD_RIGHT}
          y2={HEIGHT - PAD_BOTTOM}
          stroke="var(--color-border)"
        />
        <text x={PAD_LEFT - 8} y={yScale(max) + 4} textAnchor="end" className="equity-chart__axis-label">
          {formatCurrency(max)}
        </text>
        <text x={PAD_LEFT - 8} y={yScale(min) + 4} textAnchor="end" className="equity-chart__axis-label">
          {formatCurrency(min)}
        </text>
        <text x={PAD_LEFT} y={HEIGHT - 6} textAnchor="start" className="equity-chart__axis-label">
          {formatDate(strategy[0].date)}
        </text>
        <text x={WIDTH - PAD_RIGHT} y={HEIGHT - 6} textAnchor="end" className="equity-chart__axis-label">
          {formatDate(strategy[n - 1].date)}
        </text>
        <path d={buildPath(buyHoldValues, xScale, yScale)} fill="none" stroke="var(--color-text-faint)" strokeWidth="1.5" strokeDasharray="4 3" />
        <path d={buildPath(strategyValues, xScale, yScale)} fill="none" stroke="var(--color-accent)" strokeWidth="2" />
      </svg>
    </div>
  );
}
