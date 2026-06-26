// Live trade-signal panel: shows the actionable entry/stop/target plan derived
// from order-book density + ML prediction.

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
  if (!data) {
    return (
      <div className="body muted">
        {loading ? "Loading signal…" : "No signal yet. Select a pair and enable LIVE."}
      </div>
    );
  }
  const sig = data.signal || {};
  const action = sig.action || "flat";
  const isTrade = action === "long" || action === "short";

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
                <span className="muted">Entry</span>
                <span style={{ textAlign: "right" }}>{fmt(sig.entry)}</span>
                <span />
              </div>
              <div className="bar-row">
                <span className="muted">Stop</span>
                <span className="red" style={{ textAlign: "right" }}>
                  {fmt(sig.stop)}
                </span>
                <span className="red">-{fmt(sig.risk_pct)}%</span>
              </div>
              <div className="bar-row">
                <span className="muted">Target</span>
                <span className="green" style={{ textAlign: "right" }}>
                  {fmt(sig.target)}
                </span>
                <span className="green">+{fmt(sig.reward_pct)}%</span>
              </div>
            </>
          ) : (
            <div className="muted" style={{ fontSize: 12 }}>
              {sig.reason || "No confluence between density and ML — staying flat."}
            </div>
          )}
        </div>
      </div>

      {isTrade && (
        <div className="chips" style={{ marginBottom: 12 }}>
          <div className="chip">
            <div className="k">Risk / Reward</div>
            <div className="v">{sig.risk_reward ? `1:${fmt(sig.risk_reward, 2)}` : "—"}</div>
          </div>
          <div className="chip">
            <div className="k">Confidence</div>
            <div className="v">{sig.confidence != null ? `${fmt(sig.confidence * 100, 0)}%` : "—"}</div>
          </div>
          <div className="chip">
            <div className="k">ML bias</div>
            <div className="v" style={{ fontSize: 14 }}>
              {sig.ml_direction ? sig.ml_direction.toUpperCase() : "n/a"}
            </div>
          </div>
          <div className="chip">
            <div className="k">OB imbalance</div>
            <div className="v" style={{ fontSize: 14 }}>
              {sig.imbalance != null ? `${fmt(sig.imbalance * 100, 0)}%` : "—"}
            </div>
          </div>
        </div>
      )}

      {sig.bounce?.detected && (
        <div className="banner" style={{ margin: "0 0 10px" }}>
          Bounce setup: price near {sig.bounce.side} wall @ {fmt(sig.bounce.wall?.price)}{" "}
          ({fmt(sig.bounce.distance_pct, 2)}% away, z={fmt(sig.bounce.wall?.zscore, 1)})
        </div>
      )}

      {sig.rationale?.length > 0 && (
        <div>
          <h4 style={{ margin: "6px 0 6px", color: "var(--muted)", fontSize: 11 }}>
            WHY (confluence)
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
          ? `Model acc ${fmt(data.model_accuracy * 100, 1)}%`
          : "No ML model trained for this pair (density-only signal)."}
        {data.backtest?.win_rate != null &&
          ` · backtest win-rate ${fmt(data.backtest.win_rate, 1)}% over ${data.backtest.n_trades} trades`}
      </div>
    </div>
  );
}
