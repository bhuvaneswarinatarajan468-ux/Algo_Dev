import { useState, useMemo } from 'react';
import './TradesTable.css';

export default function PerStockTable({ rows }) {
  const [sortDir, setSortDir] = useState('desc');

  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => (sortDir === 'desc' ? b.return_pct - a.return_pct : a.return_pct - b.return_pct));
    return copy;
  }, [rows, sortDir]);

  if (rows.length === 0) {
    return <p className="helper-text">No stocks produced a trade in this period.</p>;
  }

  return (
    <div className="signals-table-wrap">
      <table className="signals-table trades-table">
        <thead>
          <tr>
            <th scope="col">Symbol</th>
            <th scope="col" className="num">Trades</th>
            <th scope="col">
              <button
                type="button"
                className="per-stock-sort-btn"
                onClick={() => setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'))}
              >
                Return {sortDir === 'desc' ? '↓' : '↑'}
              </button>
            </th>
            <th scope="col" className="num">P&amp;L</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr key={r.symbol}>
              <th scope="row">{r.symbol}</th>
              <td className="num">{r.num_trades}</td>
              <td className={'num ' + (r.return_pct >= 0 ? 'trades-table__gain' : 'trades-table__loss')}>
                {r.return_pct >= 0 ? '+' : ''}
                {r.return_pct.toFixed(2)}%
              </td>
              <td className="num">{r.pnl.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
