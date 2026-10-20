const WIDTH = 104;
const HEIGHT = 30;
const PAD_Y = 3;

function buildPath(values, xScale, yScale) {
  let d = '';
  let drawing = false;
  values.forEach((v, i) => {
    if (v == null) {
      drawing = false;
      return;
    }
    const x = xScale(i);
    const y = yScale(v);
    d += drawing ? ` L ${x} ${y}` : ` M ${x} ${y}`;
    drawing = true;
  });
  return d.trim();
}

export default function Sparkline({ smaShort, smaLong, crossoverIndex, signal }) {
  const n = smaShort.length;
  if (n === 0) {
    return <span className="helper-text">—</span>;
  }

  const allValues = [...smaShort, ...smaLong].filter((v) => v != null);
  if (allValues.length === 0) {
    return <span className="helper-text">—</span>;
  }

  const min = Math.min(...allValues);
  const max = Math.max(...allValues);
  const range = max - min || 1;

  const xScale = (i) => (n === 1 ? WIDTH / 2 : (i / (n - 1)) * WIDTH);
  const yScale = (v) => HEIGHT - PAD_Y - ((v - min) / range) * (HEIGHT - PAD_Y * 2);

  const shortPath = buildPath(smaShort, xScale, yScale);
  const longPath = buildPath(smaLong, xScale, yScale);

  const accentVar = signal === 'bullish' ? 'var(--color-bullish-strong)' : 'var(--color-bearish-strong)';

  const dot =
    crossoverIndex != null && smaShort[crossoverIndex] != null
      ? { x: xScale(crossoverIndex), y: yScale(smaShort[crossoverIndex]) }
      : null;

  return (
    <svg
      width={WIDTH}
      height={HEIGHT}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="img"
      aria-label={`${signal === 'bullish' ? 'Bullish' : 'Bearish'} trend sparkline`}
    >
      <path d={longPath} fill="none" stroke="var(--color-text-faint)" strokeWidth="1.25" strokeDasharray="2 2" />
      <path d={shortPath} fill="none" stroke={accentVar} strokeWidth="1.5" />
      {dot && <circle cx={dot.x} cy={dot.y} r="2.4" fill={accentVar} />}
    </svg>
  );
}
