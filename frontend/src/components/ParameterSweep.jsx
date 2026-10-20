import { useState } from 'react';
import './TradesTable.css';
import './ParameterSweep.css';
import { runParameterSweep, SessionExpiredError } from '../api';

export default function ParameterSweep({ form, onSessionExpired }) {
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);

  const disabled = form.symbol === 'ALL';

  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      const res = await runParameterSweep({
        symbol: form.symbol,
        start: form.start,
        end: form.end,
        capital: form.capital,
        allow_short: form.allowShort,
        costs: form.costs,
      });
      setResults(res.results);
    } catch (err) {
      if (err instanceof SessionExpiredError) {
        onSessionExpired();
        return;
      }
      setError(err.message || 'Sweep failed');
    } finally {
      setRunning(false);
    }
  }

  return (
    <details className="disclosure parameter-sweep">
      <summary>Parameter sweep (optional)</summary>
      <div className="disclosure-content">
        <p className="helper-text">
          Tests a grid of short/long SMA combinations, splitting the period
          into an in-sample window (first 70%) and an out-of-sample window
          (last 30%). A combination that only looks good in-sample is
          overfit - compare both columns. Runs on a single selected stock.
        </p>
        {disabled ? (
          <p className="helper-text">Select a single stock above (not "All Nifty 100") to run a sweep.</p>
        ) : (
          <button type="button" className="btn btn-secondary" onClick={handleRun} disabled={running}>
            {running ? 'Running sweep…' : 'Run parameter sweep'}
          </button>
        )}
        {error && (
          <p className="error-text" role="alert">
            {error}
          </p>
        )}
        {results && results.length > 0 && (
          <div className="signals-table-wrap parameter-sweep__table-wrap">
            <table className="signals-table trades-table">
              <thead>
                <tr>
                  <th scope="col">Short</th>
                  <th scope="col">Long</th>
                  <th scope="col" className="num">In-sample return</th>
                  <th scope="col" className="num">In-sample trades</th>
                  <th scope="col" className="num">Out-of-sample return</th>
                  <th scope="col" className="num">Out-of-sample trades</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr key={`${r.short}-${r.long}`}>
                    <td>{r.short}</td>
                    <td>{r.long}</td>
                    <td className={'num ' + (r.in_sample_return_pct >= 0 ? 'trades-table__gain' : 'trades-table__loss')}>
                      {r.in_sample_return_pct.toFixed(2)}%
                    </td>
                    <td className="num">{r.in_sample_trades}</td>
                    <td className={'num ' + (r.out_sample_return_pct >= 0 ? 'trades-table__gain' : 'trades-table__loss')}>
                      {r.out_sample_return_pct.toFixed(2)}%
                    </td>
                    <td className="num">{r.out_sample_trades}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {results && results.length === 0 && <p className="helper-text">No valid short/long combinations produced trades.</p>}
      </div>
    </details>
  );
}
