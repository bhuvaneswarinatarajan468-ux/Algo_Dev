import '../screens/screens.css';
import './BacktestForm.css';

const COST_FIELDS = [
  { key: 'brokerage_pct', label: 'Brokerage % (per side)' },
  { key: 'stt_pct', label: 'STT % (per side)' },
  { key: 'exchange_pct', label: 'Exchange charges % (per side)' },
  { key: 'gst_pct', label: 'GST % (on brokerage + exchange)' },
  { key: 'stamp_duty_pct', label: 'Stamp duty % (buy side only)' },
  { key: 'slippage_pct', label: 'Slippage % (per side)' },
];

function approxCostPct(costs) {
  const gstOnFees = (costs.gst_pct / 100) * (costs.brokerage_pct + costs.exchange_pct);
  const buy = costs.brokerage_pct + costs.stt_pct + costs.exchange_pct + costs.stamp_duty_pct + costs.slippage_pct + gstOnFees;
  const sell = costs.brokerage_pct + costs.stt_pct + costs.exchange_pct + costs.slippage_pct + gstOnFees;
  return { buy, sell };
}

export default function BacktestForm({ form, onChange, symbols, onRun, running, validationError }) {
  function setField(field) {
    return (e) => {
      const raw = e.target.value;
      const value = e.target.type === 'number' ? (raw === '' ? '' : Number(raw)) : raw;
      onChange({ ...form, [field]: value });
    };
  }

  function setCostField(key) {
    return (e) => {
      const value = e.target.value === '' ? 0 : Number(e.target.value);
      onChange({ ...form, costs: { ...form.costs, [key]: value } });
    };
  }

  const approx = approxCostPct(form.costs);

  return (
    <div className="backtest-form">
      <div className="backtest-form__grid">
        <div className="form-field">
          <label htmlFor="bt-symbol">Stock</label>
          <select id="bt-symbol" value={form.symbol} onChange={setField('symbol')}>
            <option value="ALL">All Nifty 100</option>
            {symbols.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="bt-short">Short SMA</label>
          <input id="bt-short" type="number" min={2} max={250} value={form.short} onChange={setField('short')} />
        </div>
        <div className="form-field">
          <label htmlFor="bt-long">Long SMA</label>
          <input id="bt-long" type="number" min={2} max={250} value={form.long} onChange={setField('long')} />
        </div>
        <div className="form-field">
          <label htmlFor="bt-start">Start date</label>
          <input id="bt-start" type="date" value={form.start} onChange={setField('start')} />
        </div>
        <div className="form-field">
          <label htmlFor="bt-end">End date</label>
          <input id="bt-end" type="date" value={form.end} onChange={setField('end')} />
        </div>
        <div className="form-field">
          <label htmlFor="bt-capital">
            {form.symbol === 'ALL' ? 'Total capital (₹)' : 'Capital per trade (₹)'}
          </label>
          <input id="bt-capital" type="number" min={1000} step={1000} value={form.capital} onChange={setField('capital')} />
        </div>
      </div>

      <label className="backtest-form__checkbox">
        <input
          type="checkbox"
          checked={form.allowShort}
          onChange={(e) => onChange({ ...form, allowShort: e.target.checked })}
        />
        Also short on bearish crossovers
      </label>
      {form.allowShort && (
        <p className="helper-text backtest-form__short-note">
          Shorting delivery stocks in India isn't possible - this simulates an
          intraday-style short only.
        </p>
      )}

      <details className="disclosure">
        <summary>Trading costs (editable)</summary>
        <div className="disclosure-content backtest-form__costs">
          <div className="backtest-form__grid">
            {COST_FIELDS.map((f) => (
              <div className="form-field" key={f.key}>
                <label htmlFor={`cost-${f.key}`}>{f.label}</label>
                <input
                  id={`cost-${f.key}`}
                  type="number"
                  step="0.001"
                  min={0}
                  value={form.costs[f.key]}
                  onChange={setCostField(f.key)}
                />
              </div>
            ))}
          </div>
          <p className="helper-text">
            Approximate total cost: <strong>{approx.buy.toFixed(3)}%</strong> on buy,{' '}
            <strong>{approx.sell.toFixed(3)}%</strong> on sell. [VERIFY] These are
            illustrative defaults for Indian equity delivery trades - confirm
            current STT, stamp duty, and GST rates before relying on them.
          </p>
        </div>
      </details>

      <button type="button" className="btn btn-primary backtest-form__run" onClick={onRun} disabled={running || !!validationError}>
        {running ? 'Running…' : 'Run Backtest'}
      </button>
      {validationError && (
        <p className="error-text" role="alert">
          {validationError}
        </p>
      )}
    </div>
  );
}
