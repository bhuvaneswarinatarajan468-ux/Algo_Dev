import { useMemo, useState } from 'react';
import './screens.css';
import './SignalsTab.css';
import SignalsControls from '../components/SignalsControls';
import SignalFilterBar from '../components/SignalFilterBar';
import SignalsTable from '../components/SignalsTable';
import { getSignals, SessionExpiredError } from '../api';

const DEFAULT_PARAMS = { short: 6, long: 30, lookback: 20 };

function formatTime(date) {
  return date.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
}

export default function SignalsTab({ onSessionExpired }) {
  const [params, setParams] = useState(DEFAULT_PARAMS);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [scannedAt, setScannedAt] = useState(null);
  const [filter, setFilter] = useState('all');

  const validationError =
    params.short !== '' && params.long !== '' && Number(params.short) >= Number(params.long)
      ? 'Short SMA must be less than Long SMA.'
      : null;

  async function handleScan() {
    if (validationError) return;
    setScanning(true);
    setError(null);
    try {
      const result = await getSignals(params);
      setData(result);
      setScannedAt(new Date());
      setFilter('all');
    } catch (err) {
      if (err instanceof SessionExpiredError) {
        onSessionExpired();
        return;
      }
      setError(err.message || 'Scan failed');
    } finally {
      setScanning(false);
    }
  }

  const counts = useMemo(() => {
    if (!data) return { all: 0, bullish: 0, bearish: 0 };
    const bullish = data.results.filter((r) => r.signal === 'bullish').length;
    const bearish = data.results.filter((r) => r.signal === 'bearish').length;
    return { all: data.results.length, bullish, bearish };
  }, [data]);

  const filteredRows = useMemo(() => {
    if (!data) return [];
    if (filter === 'all') return data.results;
    return data.results.filter((r) => r.signal === filter);
  }, [data, filter]);

  return (
    <div className="signals-tab">
      <SignalsControls
        params={params}
        onChange={setParams}
        onScan={handleScan}
        scanning={scanning}
        validationError={validationError}
      />

      {scanning && (
        <div className="signals-tab__banner">
          Scanning the Nifty 100… the first scan can take about a minute
          because Kite limits how fast we can request history. Repeat scans
          within 10 minutes are instant.
        </div>
      )}

      {error && (
        <div className="signals-tab__banner signals-tab__banner--error" role="alert">
          {error}
        </div>
      )}

      {data && !scanning && (
        <>
          <div className="signals-tab__summary">
            <SignalFilterBar counts={counts} active={filter} onChange={setFilter} />
            <p className="signals-tab__scan-line helper-text">
              Scanned {data.analyzed} of {data.total} stocks at {formatTime(scannedAt)}
              {data.skipped.length > 0 && <> · {data.skipped.length} skipped</>}
              {data.failed.length > 0 && <> · {data.failed.length} failed</>}
            </p>
          </div>

          {counts.all === 0 ? (
            <div className="signals-tab__empty">
              <p>No crossovers in this window.</p>
              <p className="helper-text">Try a longer look-back period.</p>
            </div>
          ) : filteredRows.length === 0 ? (
            <div className="signals-tab__empty">
              <p>No {filter} signals.</p>
              <p className="helper-text">Switch the filter to see other signals.</p>
            </div>
          ) : (
            <SignalsTable rows={filteredRows} short={data.params.short} long={data.params.long} />
          )}

          <p className="signals-tab__note helper-text">
            Signals are most reliable after market close - during market
            hours, the day's candle is still forming and can flip before the
            close.
          </p>
        </>
      )}

      {!data && !scanning && !error && (
        <p className="helper-text">Click "Scan Nifty 100" to look for crossovers.</p>
      )}
    </div>
  );
}
