import './BacktestSummary.css';

function Stat({ label, value, tone }) {
  return (
    <div className="stat-tile">
      <div className="stat-tile__label">{label}</div>
      <div className={'stat-tile__value num' + (tone ? ` stat-tile__value--${tone}` : '')}>{value}</div>
    </div>
  );
}

function pctTone(v) {
  if (v == null) return undefined;
  return v > 0 ? 'bullish' : v < 0 ? 'bearish' : undefined;
}

function fmtPct(v) {
  return v == null ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(2)}%`;
}

export default function BacktestSummary({ summary }) {
  return (
    <div className="stat-grid">
      <Stat label="Total return" value={fmtPct(summary.total_return_pct)} tone={pctTone(summary.total_return_pct)} />
      <Stat label="CAGR" value={fmtPct(summary.cagr_pct)} tone={pctTone(summary.cagr_pct)} />
      <Stat label="Buy & hold return" value={fmtPct(summary.buy_hold_return_pct)} tone={pctTone(summary.buy_hold_return_pct)} />
      <Stat label="Trades" value={summary.num_trades} />
      <Stat label="Win rate" value={summary.num_trades ? `${summary.win_rate_pct.toFixed(1)}%` : '—'} />
      <Stat label="Avg win" value={fmtPct(summary.avg_win_pct)} tone="bullish" />
      <Stat label="Avg loss" value={fmtPct(summary.avg_loss_pct)} tone="bearish" />
      <Stat label="Profit factor" value={summary.profit_factor != null ? summary.profit_factor.toFixed(2) : '—'} />
      <Stat label="Max drawdown" value={fmtPct(summary.max_drawdown_pct)} tone="bearish" />
    </div>
  );
}
