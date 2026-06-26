import { useEffect, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth.jsx";
import { useT } from "../i18n.jsx";

const pct = (v) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`);
// Values already expressed in percent (e.g. backtest win-rate / expectancy).
const pctRaw = (v, d = 1) => (v == null ? "—" : `${Number(v).toFixed(d)}%`);
const num = (v, d = 2) => (v == null ? "—" : Number(v).toFixed(d));
const fmtTime = (iso) => {
  try {
    return new Date(iso).toLocaleString();
  } catch (_) {
    return iso;
  }
};

function actionClass(a) {
  const v = (a || "").toLowerCase();
  if (v.includes("long") || v === "up") return "green";
  if (v.includes("short") || v === "down") return "red";
  return "yellow";
}

export default function Cabinet() {
  const { t } = useT();
  const { user } = useAuth();
  const [overview, setOverview] = useState(null);
  const [signals, setSignals] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    Promise.all([api.metricsOverview(), api.metricsSignals(40)])
      .then(([o, s]) => {
        if (!alive) return;
        setOverview(o);
        setSignals(s);
      })
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, []);

  const perPair = overview?.per_pair || [];
  const recent = signals?.recent || [];
  const byAction = signals?.by_action || {};

  return (
    <div className="view">
      <div className="panel">
        <h3>
          <span>{t("cabinet.title")}</span>
          <span className="muted">
            {t("cabinet.welcome", { name: user?.display_name || user?.email || "" })}
          </span>
        </h3>
        <div className="body">
          {error && <div className="error">⚠ {error}</div>}
          <div className="chips">
            <div className="chip">
              <div className="k">{t("cabinet.pairsTrained")}</div>
              <div className="v">{overview?.pairs_trained ?? "—"}</div>
            </div>
            <div className="chip">
              <div className="k">{t("cabinet.pairsProfitable")}</div>
              <div className="v green">{overview?.pairs_profitable ?? "—"}</div>
            </div>
            <div className="chip">
              <div className="k">{t("cabinet.avgAcc")}</div>
              <div className="v">{pct(overview?.avg_accuracy)}</div>
            </div>
            <div className="chip">
              <div className="k">{t("cabinet.avgF1")}</div>
              <div className="v">{num(overview?.avg_macro_f1, 3)}</div>
            </div>
            <div className="chip">
              <div className="k">{t("cabinet.totalRuns")}</div>
              <div className="v">{overview?.total_training_runs ?? "—"}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="panel">
        <h3>{t("cabinet.perPair")}</h3>
        <div className="body">
          {perPair.length === 0 ? (
            <div className="muted">{t("cabinet.empty")}</div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>{t("cabinet.col.pair")}</th>
                  <th>{t("cabinet.col.acc")}</th>
                  <th>{t("cabinet.col.f1")}</th>
                  <th>{t("cabinet.col.pf")}</th>
                  <th>{t("cabinet.col.winrate")}</th>
                  <th>{t("cabinet.col.exp")}</th>
                  <th>{t("cabinet.col.trades")}</th>
                  <th>{t("cabinet.col.updated")}</th>
                </tr>
              </thead>
              <tbody>
                {perPair.map((p) => (
                  <tr key={p.id}>
                    <td>{p.symbol}</td>
                    <td>{pct(p.accuracy)}</td>
                    <td>{num(p.macro_f1, 3)}</td>
                    <td className={(p.profit_factor || 0) > 1 ? "green" : "red"}>
                      {num(p.profit_factor)}
                    </td>
                    <td>{pctRaw(p.win_rate)}</td>
                    <td className={(p.expectancy || 0) >= 0 ? "green" : "red"}>
                      {pctRaw(p.expectancy, 3)}
                    </td>
                    <td>{p.trades ?? "—"}</td>
                    <td className="muted">{fmtTime(p.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="panel">
        <h3>
          <span>{t("cabinet.signalsTitle")}</span>
          <span className="muted">
            {t("cabinet.signalsByAction", {
              long: byAction.long || 0,
              short: byAction.short || 0,
              flat: byAction.flat || 0,
            })}
          </span>
        </h3>
        <div className="body">
          {recent.length === 0 ? (
            <div className="muted">{t("cabinet.signalsEmpty")}</div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>{t("cabinet.sig.time")}</th>
                  <th>{t("cabinet.sig.pair")}</th>
                  <th>{t("cabinet.sig.action")}</th>
                  <th>{t("cabinet.sig.entry")}</th>
                  <th>{t("cabinet.sig.conf")}</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((s) => (
                  <tr key={s.id}>
                    <td className="muted">{fmtTime(s.created_at)}</td>
                    <td>{s.symbol}</td>
                    <td className={actionClass(s.action)}>{(s.action || "").toUpperCase()}</td>
                    <td>{s.entry == null ? "—" : num(s.entry, 4)}</td>
                    <td>{pct(s.ml_confidence)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
