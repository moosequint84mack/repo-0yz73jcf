// Multi-pair screener: batch-train all pairs and show per-pair training +
// trade-accuracy analytics in one table.

import { useT } from "../i18n.jsx";

function fmt(n, d = 1) {
  if (n == null || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString(undefined, {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
}

export default function ScreenerPanel({
  symbols,
  results,
  running,
  onTrainAll,
  onSelect,
  current,
}) {
  const { t } = useT();
  return (
    <div className="body">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <span className="muted" style={{ fontSize: 12 }}>
          {t("screener.hint")}
        </span>
        <button onClick={onTrainAll} disabled={running}>
          {running && <span className="spinner" />}
          {running ? t("screener.training") : t("screener.trainAll", { n: symbols.length })}
        </button>
      </div>

      <table>
        <thead>
          <tr>
            <th>{t("screener.col.pair")}</th>
            <th>{t("screener.col.acc")}</th>
            <th>{t("screener.col.trades")}</th>
            <th>{t("screener.col.winrate")}</th>
            <th>{t("screener.col.pf")}</th>
            <th>{t("screener.col.exp")}</th>
          </tr>
        </thead>
        <tbody>
          {symbols.map((s) => {
            const r = results?.[s];
            const selected = s === current;
            return (
              <tr
                key={s}
                onClick={() => onSelect(s)}
                style={{ cursor: "pointer", background: selected ? "var(--panel-2)" : "" }}
              >
                <td style={{ fontWeight: selected ? 700 : 400 }}>{s}</td>
                {r?.ok ? (
                  <>
                    <td>{fmt(r.accuracy * 100, 1)}%</td>
                    <td>{r.n_trades ?? "—"}</td>
                    <td className={r.win_rate >= 50 ? "green" : r.win_rate != null ? "red" : ""}>
                      {r.win_rate != null ? `${fmt(r.win_rate, 1)}%` : "—"}
                    </td>
                    <td className={r.profit_factor >= 1 ? "green" : r.profit_factor != null ? "red" : ""}>
                      {r.profit_factor != null ? fmt(r.profit_factor, 2) : "—"}
                    </td>
                    <td className={r.expectancy_pct >= 0 ? "green" : "red"}>
                      {r.expectancy_pct != null ? `${fmt(r.expectancy_pct, 3)}%` : "—"}
                    </td>
                  </>
                ) : r && !r.ok ? (
                  <td colSpan={5} className="red" style={{ textAlign: "left" }}>
                    {r.error}
                  </td>
                ) : (
                  <td colSpan={5} className="muted" style={{ textAlign: "left" }}>
                    {t("screener.notTrained")}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
