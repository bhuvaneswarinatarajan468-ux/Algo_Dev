export function downloadTradesCsv(trades, filename) {
  const headers = ['symbol', 'type', 'entry_date', 'entry_price', 'exit_date', 'exit_price', 'return_pct', 'holding_days', 'exit_reason'];
  const rows = trades.map((t) => headers.map((h) => t[h]).join(','));
  const csv = [headers.join(','), ...rows].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
