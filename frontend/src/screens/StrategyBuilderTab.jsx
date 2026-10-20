import { useEffect, useState } from 'react';
import './screens.css';
import './StrategyBuilderTab.css';

const STORAGE_KEY = 'algo.strategyBuilder.v1';

const STRATEGIES = [
  { id: 'nifty-straddle', index: 'Nifty', kind: 'Short Straddle' },
  { id: 'nifty-strangle', index: 'Nifty', kind: 'Short Strangle' },
  { id: 'sensex-straddle', index: 'Sensex', kind: 'Short Straddle' },
  { id: 'sensex-strangle', index: 'Sensex', kind: 'Short Strangle' },
  { id: 'banknifty-straddle', index: 'Banknifty', kind: 'Short Straddle' },
  { id: 'banknifty-strangle', index: 'Banknifty', kind: 'Short Strangle' },
];

const DEFAULT_SETTINGS = { enabled: false, lots: 1, slPercent: 20 };

function loadConfig() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

export default function StrategyBuilderTab() {
  const [config, setConfig] = useState(() => {
    const saved = loadConfig();
    const initial = {};
    for (const s of STRATEGIES) {
      initial[s.id] = { ...DEFAULT_SETTINGS, ...saved[s.id] };
    }
    return initial;
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
    } catch {
      // ignore (e.g. private browsing with storage disabled)
    }
  }, [config]);

  function updateStrategy(id, patch) {
    setConfig((prev) => ({ ...prev, [id]: { ...prev[id], ...patch } }));
  }

  return (
    <div className="strategy-builder-tab">
      <div className="strategy-builder-tab__banner">
        This tab only saves your strategy settings in this browser - it does
        not place, modify, or cancel any orders.
      </div>

      <section className="profile-card">
        <h2 className="profile-card__title">Entry &amp; exit rules (all straddles/strangles)</h2>
        <ul className="strategy-builder-tab__rules">
          <li>Time of entry: <strong>10:00 AM</strong> - strict, no early/late entry.</li>
          <li>Time of exit: <strong>exactly 3:00 PM</strong> - strict square-off.</li>
          <li>Strike selection: <strong>ATM</strong> for straddles. For strangles, the same rules apply but the sold CE and PE are equidistant OTM strikes instead of ATM.</li>
          <li>Sell the ATM (or OTM, for strangles) CE and PE <strong>simultaneously</strong>, not one after another.</li>
          <li>Buy deep OTM CE and PE (approx. premium ₹2-5) as a hedge, for margin benefit. No SL on these buy legs.</li>
          <li>Individual SL per sold leg (CE and PE tracked separately): a leg exits at its own SL, independent of the other.</li>
          <li>SL is adjustable per strategy below, from <strong>10% to 50%</strong> of the premium collected on that leg.</li>
          <li>If one sold leg hits its SL, move the other sold leg's SL to cost (breakeven).</li>
        </ul>
      </section>

      <div className="strategy-builder-tab__grid">
        {STRATEGIES.map((s) => {
          const settings = config[s.id];
          return (
            <section className="profile-card strategy-builder-tab__card" key={s.id}>
              <label className="strategy-builder-tab__card-header">
                <input
                  type="checkbox"
                  checked={settings.enabled}
                  onChange={(e) => updateStrategy(s.id, { enabled: e.target.checked })}
                />
                <span>
                  <span className="strategy-builder-tab__index">{s.index}</span> {s.kind}
                </span>
              </label>

              <div className="strategy-builder-tab__fields">
                <div className="form-field">
                  <label htmlFor={`${s.id}-lots`}>Lots</label>
                  <input
                    id={`${s.id}-lots`}
                    type="number"
                    min={1}
                    max={20}
                    step={1}
                    disabled={!settings.enabled}
                    value={settings.lots}
                    onChange={(e) => {
                      const v = Math.min(20, Math.max(1, Number(e.target.value) || 1));
                      updateStrategy(s.id, { lots: v });
                    }}
                  />
                </div>
                <div className="form-field">
                  <label htmlFor={`${s.id}-sl`}>SL per leg (% of premium)</label>
                  <input
                    id={`${s.id}-sl`}
                    type="number"
                    min={10}
                    max={50}
                    step={1}
                    disabled={!settings.enabled}
                    value={settings.slPercent}
                    onChange={(e) => {
                      const v = Math.min(50, Math.max(10, Number(e.target.value) || 10));
                      updateStrategy(s.id, { slPercent: v });
                    }}
                  />
                </div>
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
