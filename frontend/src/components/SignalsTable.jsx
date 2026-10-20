import SignalPill from './SignalPill';
import RecencyBar from './RecencyBar';
import Sparkline from './Sparkline';
import './SignalsTable.css';

function formatCrossedDate(isoDate) {
  const d = new Date(isoDate + 'T00:00:00');
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function formatBarsAgo(barsAgo) {
  if (barsAgo === 0) return 'today';
  if (barsAgo === 1) return '1 trading day ago';
  return `${barsAgo} trading days ago`;
}

export default function SignalsTable({ rows, short, long }) {
  return (
    <div className="signals-table-wrap">
      <table className="signals-table">
        <thead>
          <tr>
            <th scope="col">Symbol</th>
            <th scope="col">Signal</th>
            <th scope="col">Crossed</th>
            <th scope="col">Recency</th>
            <th scope="col">Trend</th>
            <th scope="col" className="num">Close</th>
            <th scope="col" className="num">SMA {short}</th>
            <th scope="col" className="num">SMA {long}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.symbol}>
              <th scope="row" className="signals-table__symbol">{row.symbol}</th>
              <td>
                <SignalPill signal={row.signal} />
              </td>
              <td>
                <div className="signals-table__crossed">
                  <span>{formatCrossedDate(row.crossover_date)}</span>
                  <span className="helper-text">{formatBarsAgo(row.bars_ago)}</span>
                </div>
              </td>
              <td>
                <RecencyBar weight={row.weight} signal={row.signal} />
              </td>
              <td>
                <Sparkline
                  smaShort={row.sparkline.sma_short}
                  smaLong={row.sparkline.sma_long}
                  crossoverIndex={row.sparkline.crossover_index}
                  signal={row.signal}
                />
              </td>
              <td className="num">{row.close.toFixed(2)}</td>
              <td className="num">{row.sma_short != null ? row.sma_short.toFixed(2) : '—'}</td>
              <td className="num">{row.sma_long != null ? row.sma_long.toFixed(2) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
