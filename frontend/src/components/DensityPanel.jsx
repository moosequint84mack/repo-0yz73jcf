// Order-book density: heatmap of notional liquidity per price bin + wall list.
import { useT } from "../i18n.jsx";

function fmt(n, d = 0) {
  if (n == null) return "—";
  return Number(n).toLocaleString("en-US", { maximumFractionDigits: d });
}

export default function DensityPanel({ ob }) {
  const { t } = useT();
  if (!ob || !ob.heatmap) return <div className="body muted">{t("density.none")}</div>;
  const { heatmap, metrics, bid_walls, ask_walls, mid } = ob;
  const max = heatmap.max_notional || 1;
  // Show bins high price -> low price (top = asks, bottom = bids).
  const bins = [...heatmap.bins].reverse();

  return (
    <div className="body">
      <div className="chips" style={{ marginBottom: 12 }}>
        <div className="chip">
          <div className="k">{t("density.mid")}</div>
          <div className="v">{fmt(mid, 2)}</div>
        </div>
        <div className="chip">
          <div className="k">{t("density.spread")}</div>
          <div className="v">{metrics.spread_pct?.toFixed(3)}%</div>
        </div>
        <div className="chip">
          <div className="k">{t("density.imbalance")}</div>
          <div className={"v " + (metrics.imbalance >= 0 ? "green" : "red")}>
            {(metrics.imbalance * 100).toFixed(1)}%
          </div>
        </div>
        <div className="chip">
          <div className="k">{t("density.walls")}</div>
          <div className="v">
            <span className="green">{bid_walls.length}</span>
            {" / "}
            <span className="red">{ask_walls.length}</span>
          </div>
        </div>
      </div>

      <div className="heatmap">
        {bins.map((b, i) => {
          const bidW = (b.bid_notional / max) * 100;
          const askW = (b.ask_notional / max) * 100;
          const isMid = mid >= b.price_low && mid < b.price_high;
          return (
            <div className="heat-row" key={i}>
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                {bidW > 0.5 && <div className="heat-bar bid" style={{ width: `${bidW}%` }} />}
              </div>
              <div className={"heat-price" + (isMid ? " mid" : "")}>{fmt(b.price_mid, 1)}</div>
              <div>
                {askW > 0.5 && <div className="heat-bar ask" style={{ width: `${askW}%` }} />}
              </div>
            </div>
          );
        })}
      </div>

      <h4 style={{ margin: "16px 0 6px", color: "var(--muted)", fontSize: 11 }}>
        {t("density.wallsTitle")}
      </h4>
      <table>
        <thead>
          <tr>
            <th>{t("density.col.side")}</th>
            <th>{t("density.col.price")}</th>
            <th>{t("density.col.size")}</th>
            <th>{t("density.col.notional")}</th>
            <th>{t("density.col.z")}</th>
          </tr>
        </thead>
        <tbody>
          {[...bid_walls, ...ask_walls]
            .sort((a, b) => b.notional - a.notional)
            .slice(0, 8)
            .map((w, i) => (
              <tr key={i}>
                <td className={w.side === "bid" ? "green" : "red"}>
                  {w.side === "bid" ? t("density.bid") : t("density.ask")}
                </td>
                <td>{fmt(w.price, 2)}</td>
                <td>{fmt(w.amount, 3)}</td>
                <td>{fmt(w.notional)}</td>
                <td className="muted">{w.zscore.toFixed(1)}</td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}
