// Cross-exchange price comparison and divergence/arbitrage hint.
function fmt(n, d = 2) {
  if (n == null) return "—";
  return Number(n).toLocaleString("en-US", { maximumFractionDigits: d });
}

export default function ComparePanel({ data }) {
  if (!data) return <div className="body muted">Loading comparison…</div>;
  const { exchanges, divergence, unavailable } = data;
  const sorted = [...exchanges].sort((a, b) => a.last - b.last);

  return (
    <div className="body">
      {divergence && (
        <div className="chips" style={{ marginBottom: 12 }}>
          <div className="chip">
            <div className="k">Avg price</div>
            <div className="v">{fmt(divergence.average)}</div>
          </div>
          <div className="chip">
            <div className="k">Spread</div>
            <div className="v yellow">{divergence.spread_pct.toFixed(3)}%</div>
          </div>
          <div className="chip">
            <div className="k">Buy / Sell</div>
            <div className="v" style={{ fontSize: 13 }}>
              <span className="green">{divergence.arb_buy}</span>
              {" → "}
              <span className="red">{divergence.arb_sell}</span>
            </div>
          </div>
        </div>
      )}
      <table>
        <thead>
          <tr>
            <th>Exchange</th>
            <th>Last</th>
            <th>Bid</th>
            <th>Ask</th>
            <th>Δ vs avg</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((e) => (
            <tr key={e.exchange}>
              <td>
                {e.exchange}
                {divergence && e.exchange === divergence.cheapest_exchange && (
                  <span className="tag green" style={{ marginLeft: 6 }}>
                    cheapest
                  </span>
                )}
                {divergence && e.exchange === divergence.priciest_exchange && (
                  <span className="tag red" style={{ marginLeft: 6 }}>
                    priciest
                  </span>
                )}
              </td>
              <td>{fmt(e.last)}</td>
              <td className="muted">{fmt(e.bid)}</td>
              <td className="muted">{fmt(e.ask)}</td>
              <td className={e.deviation_pct >= 0 ? "green" : "red"}>
                {e.deviation_pct >= 0 ? "+" : ""}
                {e.deviation_pct?.toFixed(3)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {unavailable?.length > 0 && (
        <div className="muted" style={{ marginTop: 8, fontSize: 11 }}>
          Unavailable: {unavailable.join(", ")}
        </div>
      )}
    </div>
  );
}
