import { useState } from "react";

// Sparkline for the LightGBM validation log-loss learning curve.
function LearningCurve({ curve }) {
  if (!curve || curve.length < 2) return null;
  const w = 240;
  const h = 56;
  const vals = curve.map((p) => p.val_logloss);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  const pts = curve
    .map((p, i) => {
      const x = (i / (curve.length - 1)) * w;
      const y = h - ((p.val_logloss - min) / span) * h;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <div>
      <div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>
        Validation log-loss over {curve.length} boosting rounds (lower = learning)
      </div>
      <svg width={w} height={h} style={{ display: "block" }}>
        <polyline points={pts} fill="none" stroke="#4c8dff" strokeWidth="2" />
      </svg>
    </div>
  );
}

const CLASSES = ["down", "flat", "up"];

function Confusion({ matrix, classes }) {
  if (!matrix) return null;
  const names = classes.map((c) => CLASSES[c]);
  return (
    <table style={{ marginTop: 8 }}>
      <thead>
        <tr>
          <th>actual ╲ pred</th>
          {names.map((n) => (
            <th key={n}>{n}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {matrix.map((row, i) => (
          <tr key={i}>
            <td className="muted">{names[i]}</td>
            {row.map((v, j) => (
              <td key={j} className={i === j ? "green" : ""}>
                {v}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function MLPanel({
  status,
  prediction,
  training,
  predicting,
  onTrain,
  onPredict,
}) {
  const [horizon, setHorizon] = useState(12);
  const [threshold, setThreshold] = useState(0.4); // percent in UI
  const result = status?.result;

  return (
    <div className="body">
      <div className="controls" style={{ marginBottom: 12 }}>
        <div className="field">
          <label>Horizon (candles)</label>
          <input
            type="number"
            min={1}
            max={200}
            value={horizon}
            onChange={(e) => setHorizon(+e.target.value)}
            style={{ width: 110 }}
          />
        </div>
        <div className="field">
          <label>Move threshold %</label>
          <input
            type="number"
            min={0.05}
            step={0.05}
            value={threshold}
            onChange={(e) => setThreshold(+e.target.value)}
            style={{ width: 110 }}
          />
        </div>
        <div className="field">
          <label>&nbsp;</label>
          <button
            onClick={() => onTrain({ horizon, threshold: threshold / 100 })}
            disabled={training}
          >
            {training && <span className="spinner" />}
            {training ? "Training…" : "Train / Re-train"}
          </button>
        </div>
        <div className="field">
          <label>&nbsp;</label>
          <button className="ghost" onClick={onPredict} disabled={predicting || !result}>
            {predicting && <span className="spinner" />}
            Predict next move
          </button>
        </div>
      </div>

      {prediction && (
        <div className="signal" style={{ marginBottom: 16 }}>
          <div className={"badge " + prediction.prediction}>
            {prediction.prediction.toUpperCase()}
          </div>
          <div className="probs">
            {CLASSES.map((c) => {
              const p = prediction.probabilities[c] || 0;
              const color = c === "up" ? "#16c784" : c === "down" ? "#ea3943" : "#f0b90b";
              return (
                <div className="prob-row" key={c}>
                  <span className="muted">{c}</span>
                  <div className="prob-track">
                    <div
                      className="prob-fill"
                      style={{ width: `${p * 100}%`, background: color }}
                    />
                  </div>
                  <span>{(p * 100).toFixed(0)}%</span>
                </div>
              );
            })}
            <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>
              as of {new Date(prediction.as_of).toLocaleString()} · horizon{" "}
              {prediction.horizon} candles · model acc{" "}
              {(prediction.accuracy * 100).toFixed(1)}%
            </div>
          </div>
        </div>
      )}

      {!result && (
        <div className="muted">
          No trained model yet for this symbol/exchange/timeframe. Click{" "}
          <b>Train</b> to learn patterns from ~1 month of candles.
        </div>
      )}

      {result && (
        <>
          <div className="chips" style={{ marginBottom: 12 }}>
            <div className="chip">
              <div className="k">Accuracy</div>
              <div className="v">{(result.accuracy * 100).toFixed(1)}%</div>
            </div>
            <div className="chip">
              <div className="k">Train rows</div>
              <div className="v">{result.n_train}</div>
            </div>
            <div className="chip">
              <div className="k">Test rows</div>
              <div className="v">{result.n_test}</div>
            </div>
            <div className="chip">
              <div className="k">Labels d/f/u</div>
              <div className="v" style={{ fontSize: 13 }}>
                {result.label_distribution.down}/{result.label_distribution.flat}/
                {result.label_distribution.up}
              </div>
            </div>
          </div>

          {result.backtest && result.backtest.n_trades > 0 && (
            <>
              <h4 style={{ margin: "14px 0 4px", color: "var(--muted)", fontSize: 11 }}>
                OUT-OF-SAMPLE BACKTEST (bracket trades on test set)
              </h4>
              <div className="chips" style={{ marginBottom: 12 }}>
                <div className="chip">
                  <div className="k">Trades</div>
                  <div className="v">{result.backtest.n_trades}</div>
                </div>
                <div className="chip">
                  <div className="k">Win-rate</div>
                  <div
                    className="v"
                    style={{ color: result.backtest.win_rate >= 50 ? "var(--green)" : "var(--red)" }}
                  >
                    {result.backtest.win_rate?.toFixed(1)}%
                  </div>
                </div>
                <div className="chip">
                  <div className="k">Profit factor</div>
                  <div
                    className="v"
                    style={{
                      color: result.backtest.profit_factor >= 1 ? "var(--green)" : "var(--red)",
                    }}
                  >
                    {result.backtest.profit_factor?.toFixed(2)}
                  </div>
                </div>
                <div className="chip">
                  <div className="k">Expectancy</div>
                  <div
                    className="v"
                    style={{
                      color: result.backtest.expectancy_pct >= 0 ? "var(--green)" : "var(--red)",
                      fontSize: 14,
                    }}
                  >
                    {result.backtest.expectancy_pct?.toFixed(3)}%
                  </div>
                </div>
                <div className="chip">
                  <div className="k">Max drawdown</div>
                  <div className="v red" style={{ fontSize: 14 }}>
                    {result.backtest.max_drawdown_pct?.toFixed(2)}%
                  </div>
                </div>
                <div className="chip">
                  <div className="k">Sharpe-like</div>
                  <div className="v" style={{ fontSize: 14 }}>
                    {result.backtest.sharpe_like?.toFixed(2)}
                  </div>
                </div>
              </div>
            </>
          )}

          <LearningCurve curve={result.learning_curve} />

          <h4 style={{ margin: "14px 0 4px", color: "var(--muted)", fontSize: 11 }}>
            CONFUSION MATRIX (test set)
          </h4>
          <Confusion matrix={result.confusion} classes={result.classes} />

          <h4 style={{ margin: "16px 0 4px", color: "var(--muted)", fontSize: 11 }}>
            TOP FEATURE IMPORTANCES
          </h4>
          <div className="bars">
            {Object.entries(result.feature_importances)
              .slice(0, 10)
              .map(([k, v], _i, arr) => {
                const maxv = arr[0][1] || 1;
                return (
                  <div className="bar-row" key={k}>
                    <span className="muted">{k}</span>
                    <div className="bar-track">
                      <div className="bar-fill" style={{ width: `${(v / maxv) * 100}%` }} />
                    </div>
                    <span>{Math.round(v)}</span>
                  </div>
                );
              })}
          </div>
        </>
      )}
    </div>
  );
}
