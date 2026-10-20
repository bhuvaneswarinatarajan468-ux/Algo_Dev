import './EquityChart.css';
import './DrawdownChart.css';

const WIDTH = 720;
const HEIGHT = 100;
const PAD_LEFT = 56;
const PAD_RIGHT = 16;
const PAD_TOP = 10;
const PAD_BOTTOM = 10;

export default function DrawdownChart({ points }) {
  const n = points.length;
  if (n === 0) {
    return null;
  }

  const values = points.map((p) => p.drawdown_pct);
  const min = Math.min(...values, 0);
  const innerWidth = WIDTH - PAD_LEFT - PAD_RIGHT;
  const innerHeight = HEIGHT - PAD_TOP - PAD_BOTTOM;

  const xScale = (i) => PAD_LEFT + (n === 1 ? innerWidth / 2 : (i / (n - 1)) * innerWidth);
  const yScale = (v) => PAD_TOP + (min === 0 ? 0 : (v / min) * innerHeight);

  const linePath = values.map((v, i) => `${i === 0 ? 'M' : 'L'} ${xScale(i)} ${yScale(v)}`).join(' ');
  const areaPath =
    `M ${xScale(0)} ${PAD_TOP} ` +
    values.map((v, i) => `L ${xScale(i)} ${yScale(v)}`).join(' ') +
    ` L ${xScale(n - 1)} ${PAD_TOP} Z`;

  return (
    <div className="equity-chart drawdown-chart">
      <p className="drawdown-chart__title helper-text">Drawdown</p>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="equity-chart__svg"
        role="img"
        aria-label="Drawdown from peak equity over time"
      >
        <line x1={PAD_LEFT} y1={PAD_TOP} x2={WIDTH - PAD_RIGHT} y2={PAD_TOP} stroke="var(--color-border)" />
        <text x={PAD_LEFT - 8} y={PAD_TOP + 4} textAnchor="end" className="equity-chart__axis-label">
          0%
        </text>
        <text x={PAD_LEFT - 8} y={HEIGHT - PAD_BOTTOM} textAnchor="end" className="equity-chart__axis-label">
          {min.toFixed(0)}%
        </text>
        <path d={areaPath} fill="var(--color-bearish-bg)" stroke="none" />
        <path d={linePath} fill="none" stroke="var(--color-bearish-strong)" strokeWidth="1.5" />
      </svg>
    </div>
  );
}
