// Cross-exchange price comparison and divergence/arbitrage hint.
import { useT } from "../i18n.jsx";

function fmt(n, d = 2) {
  if (n == null) return "—";
  return Number(n).toLocaleString("en-US", { maximumFractionDigits: d });
}

export default function ComparePanel({ data }) {
  const { t } = useT();
  if (!data) return <div className="body muted">{t("compare.loading")}</div>;
  const { exchanges, divergence, unavailable } = data;
  const sorted = [...exchanges].sort((a, b) => a.last - b.last);

  return (
    <div className="body">
      {divergence && (
        <div className="chips" style={{ marginBottom: 12 }}>
          <div className="chip">
            <div className="k">{t("compare.avg")}</div>
            <div className="v">{fmt(divergence.average)}</div>
          </div>
          <div className="chip">
            <div className="k">{t("compare.spread")}</div>
            <div className="v yellow">{divergence.spread_pct.toFixed(3)}%</div>
          </div>
          <div className="chip">
            <div className="k">{t("compare.buySell")}</div>
            <div className="v" style={{ fontSize: 13 }}>
              <span className="green">{divergence.arb_buy}</span>
              {" → "}
              <span className="red">{divergence.arb_sell}</span>
            </div>
          </div>
        </div>
      )}
      {divergence && divergence.arb_net_pct != null && (
        <div
          className={"arb-line " + (divergence.arb_actionable ? "green" : "muted")}
          style={{ marginBottom: 12, fontSize: 12 }}
        >
          <span className="k" style={{ fontWeight: 700, marginRight: 6 }}>
            {t("compare.arbTitle")}:
          </span>
          {divergence.arb_actionable
            ? t("compare.arbYes", {
                buy: divergence.arb_buy,
                sell: divergence.arb_sell,
                net: divergence.arb_net_pct.toFixed(3),
                gross: divergence.arb_gross_pct.toFixed(3),
                fee: divergence.arb_fee_pct.toFixed(2),
              })
            : t("compare.arbNo", {
                gross: divergence.arb_gross_pct.toFixed(3),
                fee: divergence.arb_fee_pct.toFixed(2),
              })}
        </div>
      )}
      <table>
        <thead>
          <tr>
            <th>{t("compare.col.exchange")}</th>
            <th>{t("compare.col.last")}</th>
            <th>{t("compare.col.bid")}</th>
            <th>{t("compare.col.ask")}</th>
            <th>{t("compare.col.dev")}</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((e) => (
            <tr key={e.exchange}>
              <td>
                {e.exchange}
                {divergence && e.exchange === divergence.cheapest_exchange && (
                  <span className="tag green" style={{ marginLeft: 6 }}>
                    {t("compare.cheapest")}
                  </span>
                )}
                {divergence && e.exchange === divergence.priciest_exchange && (
                  <span className="tag red" style={{ marginLeft: 6 }}>
                    {t("compare.priciest")}
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
          {t("compare.unavailable", { list: unavailable.join(", ") })}
        </div>
      )}
    </div>
  );
}
