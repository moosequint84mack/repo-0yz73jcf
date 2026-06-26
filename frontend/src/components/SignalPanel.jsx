// Live trade-signal panel: shows the actionable entry/stop/target plan derived
// from order-book density + ML prediction, plus real-leverage position sizing.

import { useT } from "../i18n.jsx";

function fmt(n, d = 2) {
  if (n == null || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString(undefined, {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
}

const ACTION_CLASS = { long: "up", short: "down", flat: "flat" };
const ACTION_LABEL = { long: "LONG", short: "SHORT", flat: "NO TRADE" };

export default function SignalPanel({ data, loading }) {
  const { t } = useT();
  if (!data) {
    return (
      <div className="body muted">
        {loading ? t("signal.loading") : t("signal.empty")}
      </div>
    );
  }
  const sig = data.signal || {};
  const action = sig.action || "flat";
  const isTrade = action === "long" || action === "short";
  const lev = sig.leverage || {};
  const levInfo = sig.leverage_info || {};

  return (
    <div className="body">
      <div className="signal" style={{ marginBottom: 14 }}>
        <div className={"badge " + (ACTION_CLASS[action] || "flat")}>
          {ACTION_LABEL[action] || "NO TRADE"}
        </div>
        <div className="probs">
          {isTrade ? (
            <>
              <div className="bar-row">
                <span className="muted">{t("signal.entry")}</span>
                <span style={{ textAlign: "right" }}>{fmt(sig.entry)}</span>
                <span />
              </div>
              <div className="bar-row">
                <span className="muted">{t("signal.stop")}</span>
                <span className="red" style={{ textAlign: "right" }}>
                  {fmt(sig.stop)}
                </span>
                <span className="red">-{fmt(sig.risk_pct)}%</span>
              </div>
              <div className="bar-row">
                <span className="muted">{t("signal.target")}</span>
                <span className="green" style={{ textAlign: "right" }}>
                  {fmt(sig.target)}
                </span>
                <span className="green">+{fmt(sig.reward_pct)}%</span>
              </div>
            </>
          ) : (
            <div className="muted" style={{ fontSize: 12 }}>
              {sig.reason || t("signal.noConfluence")}
            </div>
          )}
        </div>
      </div>

      {isTrade && (
        <div className="chips" style={{ marginBottom: 12 }}>
          <div className="chip">
            <div className="k">{t("signal.riskReward")}</div>
            <div className="v">{sig.risk_reward ? `1:${fmt(sig.risk_reward, 2)}` : "—"}</div>
          </div>
          <div className="chip">
            <div className="k">{t("signal.confidence")}</div>
            <div className="v">{sig.confidence != null ? `${fmt(sig.confidence * 100, 0)}%` : "—"}</div>
          </div>
          <div className="chip">
            <div className="k">{t("signal.mlBias")}</div>
            <div className="v" style={{ fontSize: 14 }}>
              {sig.ml_direction ? sig.ml_direction.toUpperCase() : "n/a"}
            </div>
          </div>
          <div className="chip">
            <div className="k">{t("signal.obImbalance")}</div>
            <div className="v" style={{ fontSize: 14 }}>
              {sig.imbalance != null ? `${fmt(sig.imbalance * 100, 0)}%` : "—"}
            </div>
          </div>
        </div>
      )}

      {isTrade && lev.applicable && (
        <div style={{ marginBottom: 12 }}>
          <h4 style={{ margin: "6px 0 8px", color: "var(--muted)", fontSize: 11 }}>
            {t("lev.title")}
          </h4>
          <div className="chips">
            <div className="chip">
              <div className="k">{t("lev.leverage")}</div>
              <div className="v">{fmt(lev.leverage, 1)}×</div>
            </div>
            <div className="chip">
              <div className="k">{t("lev.maxAvail")}</div>
              <div className="v">
                {lev.max_leverage_available ? `${fmt(lev.max_leverage_available, 0)}×` : "—"}
              </div>
            </div>
            <div className="chip">
              <div className="k">{t("lev.notional")}</div>
              <div className="v">${fmt(lev.notional, 0)}</div>
            </div>
            <div className="chip">
              <div className="k">{t("lev.margin")}</div>
              <div className="v">${fmt(lev.margin_required, 2)}</div>
            </div>
            <div className="chip">
              <div className="k">{t("lev.posSize")}</div>
              <div className="v" style={{ fontSize: 13 }}>{fmt(lev.position_size_base, 4)}</div>
            </div>
            <div className="chip">
              <div className="k">{t("lev.profit")}</div>
              <div className="v green">+${fmt(lev.profit_usd, 2)}</div>
            </div>
            <div className="chip">
              <div className="k">{t("lev.loss")}</div>
              <div className="v red">-${fmt(lev.loss_usd, 2)}</div>
            </div>
            <div className="chip">
              <div className="k">{t("lev.roeTarget")}</div>
              <div className="v green" style={{ fontSize: 14 }}>+{fmt(lev.roe_target_pct, 0)}%</div>
            </div>
            <div className="chip">
              <div className="k">{t("lev.liqPrice")}</div>
              <div className="v" style={{ fontSize: 13 }}>{fmt(lev.liquidation_price)}</div>
            </div>
            <div className="chip">
              <div className="k">{t("lev.liqDist")}</div>
              <div className="v" style={{ fontSize: 14 }}>{fmt(lev.liquidation_distance_pct, 2)}%</div>
            </div>
          </div>
          <div
            className="muted"
            style={{ fontSize: 11, marginTop: 6, color: lev.stop_before_liquidation ? "var(--green)" : "var(--red)" }}
          >
            {lev.stop_before_liquidation ? `✓ ${t("lev.stopSafe")}` : `⚠ ${t("lev.stopUnsafe")}`}
            {levInfo.venues_with_leverage != null &&
              ` · ${t("lev.venues", { n: levInfo.venues_with_leverage })}`}
          </div>
        </div>
      )}

      {!lev.applicable && (levInfo.max_leverage != null || levInfo.typical_leverage != null) && (
        <div style={{ marginBottom: 12 }}>
          <h4 style={{ margin: "6px 0 8px", color: "var(--muted)", fontSize: 11 }}>
            {t("lev.realTitle")}
          </h4>
          <div className="chips">
            <div className="chip">
              <div className="k">{t("lev.maxAcross")}</div>
              <div className="v">
                {levInfo.max_leverage ? `${fmt(levInfo.max_leverage, 0)}×` : "—"}
              </div>
            </div>
            <div className="chip">
              <div className="k">{t("lev.typical")}</div>
              <div className="v">
                {levInfo.typical_leverage ? `${fmt(levInfo.typical_leverage, 0)}×` : "—"}
              </div>
            </div>
            <div className="chip">
              <div className="k">{t("lev.venuesShort")}</div>
              <div className="v">{levInfo.venues_with_leverage ?? "—"}</div>
            </div>
          </div>
          <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>
            {t("lev.appliesOnTrade")}
          </div>
        </div>
      )}

      {sig.bounce?.detected && (
        <div className="banner" style={{ margin: "0 0 10px" }}>
          {t("signal.bounce", {
            side: sig.bounce.side,
            price: fmt(sig.bounce.wall?.price),
            dist: fmt(sig.bounce.distance_pct, 2),
            z: fmt(sig.bounce.wall?.zscore, 1),
          })}
        </div>
      )}

      {sig.rationale?.length > 0 && (
        <div>
          <h4 style={{ margin: "6px 0 6px", color: "var(--muted)", fontSize: 11 }}>
            {t("signal.why")}
          </h4>
          <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12, lineHeight: 1.6 }}>
            {sig.rationale.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="muted" style={{ fontSize: 11, marginTop: 10 }}>
        {data.model_trained
          ? t("signal.modelAcc", { acc: fmt(data.model_accuracy * 100, 1) })
          : t("signal.noMlModel")}
        {data.backtest?.win_rate != null &&
          t("signal.backtestWinrate", {
            wr: fmt(data.backtest.win_rate, 1),
            n: data.backtest.n_trades,
          })}
      </div>
    </div>
  );
}
