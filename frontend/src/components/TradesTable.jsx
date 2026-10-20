import './TradesTable.css';
import { downloadTradesCsv } from '../csv';

const EXIT_LABELS = {
  bullish_crossover: 'Bullish crossover',
  bearish_crossover: 'Bearish crossover',
  open_at_end: 'Open at end',
};

export default function TradesTable({ trades }) {
  if (trades.length === 0) {
    return <p className="helper-text">No trades in this period.</p>;
  }

  return (
    <div className="trades-table-wrap">
      <div className="trades-table__header">
        <h3 className="trades-table__title">Trades</h3>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => downloadTradesCsv(trades, 'algo-backtest-trades.csv')}
        >
          Download CSV
        </button>
      </div>
      <div className="signals-table-wrap">
        <table className="signals-table trades-table">
          <thead>
            <tr>
              <th scope="col">Symbol</th>
              <th scope="col">Type</th>
              <th scope="col">Entry</th>
              <th scope="col" className="num">Entry price</th>
              <th scope="col">Exit</th>
              <th scope="col" className="num">Exit price</th>
              <th scope="col" className="num">Return</th>
              <th scope="col" className="num">Days held</th>
              <th scope="col">Exit reason</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t, i) => (
              <tr key={`${t.symbol}-${t.entry_date}-${i}`}>
                <th scope="row">{t.symbol}</th>
                <td>{t.type}</td>
                <td>{t.entry_date}</td>
                <td className="num">{t.entry_price.toFixed(2)}</td>
                <td>{t.exit_date}</td>
                <td className="num">{t.exit_price.toFixed(2)}</td>
                <td className={'num ' + (t.return_pct >= 0 ? 'trades-table__gain' : 'trades-table__loss')}>
                  {t.return_pct >= 0 ? '+' : ''}
                  {t.return_pct.toFixed(2)}%
                </td>
                <td className="num">{t.holding_days}</td>
                <td>{EXIT_LABELS[t.exit_reason] || t.exit_reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
