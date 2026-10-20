import './SignalsControls.css';

export default function SignalsControls({ params, onChange, onScan, scanning, validationError }) {
  function handleField(field) {
    return (e) => {
      const value = e.target.value === '' ? '' : Number(e.target.value);
      onChange({ ...params, [field]: value });
    };
  }

  return (
    <div className="signals-controls">
      <div className="signals-controls__fields">
        <div className="form-field form-field--compact">
          <label htmlFor="short-sma">Short SMA</label>
          <input
            id="short-sma"
            type="number"
            min={2}
            max={250}
            value={params.short}
            onChange={handleField('short')}
          />
        </div>
        <div className="form-field form-field--compact">
          <label htmlFor="long-sma">Long SMA</label>
          <input
            id="long-sma"
            type="number"
            min={2}
            max={250}
            value={params.long}
            onChange={handleField('long')}
          />
        </div>
        <div className="form-field form-field--compact">
          <label htmlFor="lookback">Look back (trading days)</label>
          <input
            id="lookback"
            type="number"
            min={1}
            max={120}
            value={params.lookback}
            onChange={handleField('lookback')}
          />
        </div>
        <button
          type="button"
          className="btn btn-primary signals-controls__scan"
          onClick={onScan}
          disabled={scanning || !!validationError}
        >
          {scanning ? 'Scanning…' : 'Scan Nifty 100'}
        </button>
      </div>
      {validationError && (
        <p className="error-text" role="alert">
          {validationError}
        </p>
      )}
    </div>
  );
}
