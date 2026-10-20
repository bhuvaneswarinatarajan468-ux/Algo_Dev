import { useEffect, useRef, useState } from 'react';
import './screens.css';
import './BacktestTab.css';
import BacktestForm from '../components/BacktestForm';
import BacktestSummary from '../components/BacktestSummary';
import EquityChart from '../components/EquityChart';
import DrawdownChart from '../components/DrawdownChart';
import TradesTable from '../components/TradesTable';
import PerStockTable from '../components/PerStockTable';
import ParameterSweep from '../components/ParameterSweep';
import {
  getSymbols,
  runSingleBacktest,
  startUniverseBacktest,
  getBacktestJob,
  SessionExpiredError,
} from '../api';

const DEFAULT_COSTS = {
  brokerage_pct: 0,
  stt_pct: 0.1,
  exchange_pct: 0.00345,
  gst_pct: 18,
  stamp_duty_pct: 0.015,
  slippage_pct: 0.05,
};

function isoDaysAgo(days) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

const DEFAULT_FORM = {
  symbol: 'ALL',
  short: 6,
  long: 30,
  start: isoDaysAgo(365 * 3),
  end: isoDaysAgo(0),
  capital: 100000,
  allowShort: false,
  costs: DEFAULT_COSTS,
};

const POLL_MS = 1500;

export default function BacktestTab({ onSessionExpired }) {
  const [symbols, setSymbols] = useState([]);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [running, setRunning] = useState(false);
  const [jobProgress, setJobProgress] = useState(null);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const pollRef = useRef(null);

  useEffect(() => {
    getSymbols()
      .then((r) => setSymbols([...r.symbols].sort()))
      .catch(() => {});
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, []);

  const validationError = Number(form.short) >= Number(form.long) ? 'Short SMA must be less than Long SMA.' : null;

  function stopPolling() {
    if (pollRef.current) {
      clearTimeout(pollRef.current);
      pollRef.current = null;
    }
  }

  function pollJob(jobId) {
    getBacktestJob(jobId)
      .then((job) => {
        setJobProgress(job.progress);
        if (job.status === 'done') {
          setResult({ mode: 'all', data: job.result });
          setRunning(false);
        } else if (job.status === 'error') {
          setError(job.error || 'Backtest failed');
          setRunning(false);
        } else {
          pollRef.current = setTimeout(() => pollJob(jobId), POLL_MS);
        }
      })
      .catch((err) => {
        setError(err.message || 'Could not check backtest progress');
        setRunning(false);
      });
  }

  async function handleRun() {
    if (validationError) return;
    stopPolling();
    setRunning(true);
    setError(null);
    setResult(null);
    setJobProgress(null);

    const basePayload = {
      short: Number(form.short),
      long: Number(form.long),
      start: form.start,
      end: form.end,
      capital: Number(form.capital),
      allow_short: form.allowShort,
      costs: form.costs,
    };

    try {
      if (form.symbol === 'ALL') {
        const { job_id } = await startUniverseBacktest(basePayload);
        pollJob(job_id);
      } else {
        const data = await runSingleBacktest({ ...basePayload, symbol: form.symbol });
        setResult({ mode: 'single', data });
        setRunning(false);
      }
    } catch (err) {
      if (err instanceof SessionExpiredError) {
        onSessionExpired();
        return;
      }
      setError(err.message || 'Backtest failed');
      setRunning(false);
    }
  }

  return (
    <div className="backtest-tab">
      <BacktestForm
        form={form}
        onChange={setForm}
        symbols={symbols}
        onRun={handleRun}
        running={running}
        validationError={validationError}
      />

      <div className="backtest-tab__notes">
        <p>
          Backtests use today's Nifty 100 members, so results suffer from{' '}
          <strong>survivorship bias</strong>.
        </p>
        <p>Past performance does not predict future results.</p>
        <p>
          Optimising SMA periods on the same data overfits - use the
          parameter sweep below to check whether a good result holds up
          out-of-sample.
        </p>
      </div>

      {running && (
        <div className="backtest-tab__banner">
          {jobProgress
            ? `Running: ${jobProgress.done} of ${jobProgress.total} stocks…`
            : 'Running backtest…'}
        </div>
      )}

      {error && (
        <div className="backtest-tab__banner backtest-tab__banner--error" role="alert">
          {error}
        </div>
      )}

      {result && (
        <div className="backtest-tab__results">
          <BacktestSummary summary={result.data.summary} />
          <EquityChart strategy={result.data.equity_curve} buyHold={result.data.buy_hold_curve} />
          <DrawdownChart points={result.data.drawdown} />

          {result.mode === 'all' && (
            <>
              <p className="helper-text">{result.data.assumption}</p>
              <h3 className="backtest-tab__subheading">Per-stock results</h3>
              <PerStockTable rows={result.data.per_stock} />
            </>
          )}

          <TradesTable trades={result.data.trades} />
        </div>
      )}

      <ParameterSweep form={form} onSessionExpired={onSessionExpired} />
    </div>
  );
}
