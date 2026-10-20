import './SignalPill.css';

export default function SignalPill({ signal }) {
  const bullish = signal === 'bullish';
  return (
    <span className={'signal-pill ' + (bullish ? 'signal-pill--bullish' : 'signal-pill--bearish')}>
      {bullish ? 'Bullish' : 'Bearish'}
    </span>
  );
}
