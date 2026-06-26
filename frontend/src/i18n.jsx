import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

// Lightweight i18n: a flat key → string dictionary per language, a context that
// holds the active language, and a `useT()` hook returning a `t(key, vars)`
// interpolation helper. Default language is Russian (ru).

const STRINGS = {
  ru: {
    "app.title": "КРИПТО-СКРИНЕР",
    "field.symbol": "Монета",
    "field.exchange": "Биржа",
    "field.timeframe": "Таймфрейм",
    "live.on": "● LIVE",
    "live.off": "○ ПАУЗА",
    "lang.label": "Язык",

    "screener.title": "Мульти-скринер пар",
    "screener.subtitle": "обучение и ранжирование всех пар",
    "screener.hint":
      "Обучить по одной модели на пару на всём окне истории, затем сравнить точность и качество сделок по бэктесту.",
    "screener.trainAll": "Обучить все пары ({n})",
    "screener.training": "Обучение всех пар…",
    "screener.col.pair": "Пара",
    "screener.col.acc": "Точн.",
    "screener.col.trades": "Сделки",
    "screener.col.winrate": "Win-rate",
    "screener.col.pf": "Profit factor",
    "screener.col.exp": "Ожидание",
    "screener.col.lev": "Плечо",
    "screener.notTrained": "не обучена",

    "chart.candles": "{n} свечей",

    "ml.title": "ML-сигнал и обучение",
    "ml.horizon": "Горизонт (свечей)",
    "ml.threshold": "Порог движения %",
    "ml.train": "Обучить / Переобучить",
    "ml.training": "Обучение…",
    "ml.predict": "Прогноз след. движения",
    "ml.curveLabel": "Validation log-loss за {n} раундов бустинга (ниже = учится)",
    "ml.confActualPred": "факт ╲ прогноз",
    "ml.asOf": "на {date} · горизонт {h} свечей · точность модели {acc}%",
    "ml.noModel":
      "Для этой монеты/биржи/таймфрейма модель ещё не обучена. Нажмите «Обучить», чтобы изучить паттерны за ~месяц свечей.",
    "ml.accuracy": "Точность",
    "ml.macroF1": "Macro-F1",
    "ml.trainRows": "Строк обуч.",
    "ml.testRows": "Строк тест.",
    "ml.labels": "Метки н/ф/в",
    "ml.backtestTitle": "БЭКТЕСТ ВНЕ ВЫБОРКИ (брекет-сделки на тест-сете)",
    "ml.trades": "Сделки",
    "ml.winrate": "Win-rate",
    "ml.pf": "Profit factor",
    "ml.expectancy": "Ожидание",
    "ml.maxdd": "Макс. просадка",
    "ml.sharpe": "Sharpe-подобн.",
    "ml.confusionTitle": "МАТРИЦА ОШИБОК (тест-сет)",
    "ml.featTitle": "ВАЖНОСТЬ ПРИЗНАКОВ (топ)",

    "signal.title": "Торговый сигнал",
    "signal.subtitle": "вход · стоп · цель",
    "signal.loading": "Загрузка сигнала…",
    "signal.empty": "Сигнала пока нет. Выберите пару и включите LIVE.",
    "signal.entry": "Вход",
    "signal.stop": "Стоп",
    "signal.target": "Цель",
    "signal.noConfluence": "Нет совпадения плотности и ML — остаёмся вне рынка.",
    "signal.riskReward": "Риск / Прибыль",
    "signal.confidence": "Уверенность",
    "signal.mlBias": "ML-уклон",
    "signal.obImbalance": "Дисбаланс стакана",
    "signal.bounce":
      "Отскок: цена у {side} стенки @ {price} ({dist}% до неё, z={z})",
    "signal.why": "ПОЧЕМУ (confluence)",
    "signal.modelAcc": "Точность модели {acc}%",
    "signal.noMlModel": "Модель не обучена для этой пары (сигнал только по плотности).",
    "signal.backtestWinrate": " · win-rate бэктеста {wr}% на {n} сделках",

    "lev.title": "ПЛЕЧО И РАСЧЁТ ПОЗИЦИИ (реальные данные бирж)",
    "lev.leverage": "Плечо",
    "lev.maxAvail": "Макс. на биржах",
    "lev.notional": "Объём позиции",
    "lev.posSize": "Размер (база)",
    "lev.margin": "Маржа",
    "lev.profit": "Прибыль (цель)",
    "lev.loss": "Убыток (стоп)",
    "lev.roeTarget": "ROE цель",
    "lev.roeStop": "ROE стоп",
    "lev.liqPrice": "Цена ликвидации",
    "lev.liqDist": "До ликвидации",
    "lev.equity": "Депозит",
    "lev.risk": "Риск/сделку",
    "lev.stopSafe": "Стоп срабатывает раньше ликвидации",
    "lev.stopUnsafe": "ВНИМАНИЕ: ликвидация ближе стопа",
    "lev.venues": "Источники плеча: {n} бирж",
    "lev.perExchange": "По биржам",
    "lev.none": "Нет данных по плечу (бессрочных контрактов не найдено на биржах).",
    "lev.realTitle": "РЕАЛЬНОЕ ПЛЕЧО ПО МОНЕТЕ (данные бирж)",
    "lev.maxAcross": "Макс. (все биржи)",
    "lev.typical": "Типичное",
    "lev.venuesShort": "Бирж с плечом",
    "lev.appliesOnTrade": "Плечо применяется к расчёту позиции при появлении сделки (LONG/SHORT).",

    "density.title": "Плотность стакана",
    "density.subtitle": "стенки и тепловая карта (live)",
    "density.none": "Нет данных стакана.",
    "density.mid": "Средняя",
    "density.spread": "Спред",
    "density.imbalance": "Дисбаланс",
    "density.walls": "Стенки",
    "density.wallsTitle": "КРУПНЕЙШИЕ СТЕНКИ ЛИКВИДНОСТИ",
    "density.col.side": "Сторона",
    "density.col.price": "Цена",
    "density.col.size": "Размер",
    "density.col.notional": "Объём $",
    "density.col.z": "Z",
    "density.bid": "ПОКУПКА",
    "density.ask": "ПРОДАЖА",

    "compare.title": "Сравнение бирж",
    "compare.loading": "Загрузка сравнения…",
    "compare.avg": "Сред. цена",
    "compare.spread": "Спред",
    "compare.buySell": "Купить / Продать",
    "compare.col.exchange": "Биржа",
    "compare.col.last": "Послед.",
    "compare.col.bid": "Bid",
    "compare.col.ask": "Ask",
    "compare.col.dev": "Δ к сред.",
    "compare.cheapest": "дешевле",
    "compare.priciest": "дороже",
    "compare.unavailable": "Недоступны: {list}",

    "footer":
      "Данные через публичные эндпоинты CCXT. Стенки = уровни стакана, объём которых статистически аномален (z-score). Плечо подтягивается из реальных лимитов бессрочных контрактов бирж. ML прогнозирует движение на {h} свечей вперёд (вниз / флэт / вверх). Не является финансовым советом.",
  },
  en: {
    "app.title": "CRYPTO SCREENER",
    "field.symbol": "Symbol",
    "field.exchange": "Exchange",
    "field.timeframe": "Timeframe",
    "live.on": "● LIVE",
    "live.off": "○ PAUSED",
    "lang.label": "Language",

    "screener.title": "Multi-pair screener",
    "screener.subtitle": "train & rank all pairs",
    "screener.hint":
      "Train one model per pair on the full history window, then compare accuracy and backtested trade quality.",
    "screener.trainAll": "Train all {n} pairs",
    "screener.training": "Training all pairs…",
    "screener.col.pair": "Pair",
    "screener.col.acc": "Acc",
    "screener.col.trades": "Trades",
    "screener.col.winrate": "Win-rate",
    "screener.col.pf": "Profit factor",
    "screener.col.exp": "Expectancy",
    "screener.col.lev": "Leverage",
    "screener.notTrained": "not trained",

    "chart.candles": "{n} candles",

    "ml.title": "Machine-learning signal & training",
    "ml.horizon": "Horizon (candles)",
    "ml.threshold": "Move threshold %",
    "ml.train": "Train / Re-train",
    "ml.training": "Training…",
    "ml.predict": "Predict next move",
    "ml.curveLabel": "Validation log-loss over {n} boosting rounds (lower = learning)",
    "ml.confActualPred": "actual ╲ pred",
    "ml.asOf": "as of {date} · horizon {h} candles · model acc {acc}%",
    "ml.noModel":
      "No trained model yet for this symbol/exchange/timeframe. Click Train to learn patterns from ~1 month of candles.",
    "ml.accuracy": "Accuracy",
    "ml.macroF1": "Macro-F1",
    "ml.trainRows": "Train rows",
    "ml.testRows": "Test rows",
    "ml.labels": "Labels d/f/u",
    "ml.backtestTitle": "OUT-OF-SAMPLE BACKTEST (bracket trades on test set)",
    "ml.trades": "Trades",
    "ml.winrate": "Win-rate",
    "ml.pf": "Profit factor",
    "ml.expectancy": "Expectancy",
    "ml.maxdd": "Max drawdown",
    "ml.sharpe": "Sharpe-like",
    "ml.confusionTitle": "CONFUSION MATRIX (test set)",
    "ml.featTitle": "TOP FEATURE IMPORTANCES",

    "signal.title": "Trade signal",
    "signal.subtitle": "entry · stop · target",
    "signal.loading": "Loading signal…",
    "signal.empty": "No signal yet. Select a pair and enable LIVE.",
    "signal.entry": "Entry",
    "signal.stop": "Stop",
    "signal.target": "Target",
    "signal.noConfluence": "No confluence between density and ML — staying flat.",
    "signal.riskReward": "Risk / Reward",
    "signal.confidence": "Confidence",
    "signal.mlBias": "ML bias",
    "signal.obImbalance": "OB imbalance",
    "signal.bounce":
      "Bounce setup: price near {side} wall @ {price} ({dist}% away, z={z})",
    "signal.why": "WHY (confluence)",
    "signal.modelAcc": "Model acc {acc}%",
    "signal.noMlModel": "No ML model trained for this pair (density-only signal).",
    "signal.backtestWinrate": " · backtest win-rate {wr}% over {n} trades",

    "lev.title": "LEVERAGE & POSITION SIZING (real exchange data)",
    "lev.leverage": "Leverage",
    "lev.maxAvail": "Max on exchanges",
    "lev.notional": "Notional",
    "lev.posSize": "Size (base)",
    "lev.margin": "Margin",
    "lev.profit": "Profit (target)",
    "lev.loss": "Loss (stop)",
    "lev.roeTarget": "ROE target",
    "lev.roeStop": "ROE stop",
    "lev.liqPrice": "Liquidation price",
    "lev.liqDist": "To liquidation",
    "lev.equity": "Equity",
    "lev.risk": "Risk/trade",
    "lev.stopSafe": "Stop triggers before liquidation",
    "lev.stopUnsafe": "WARNING: liquidation closer than stop",
    "lev.venues": "Leverage sources: {n} exchanges",
    "lev.perExchange": "Per exchange",
    "lev.none": "No leverage data (no perpetual markets found on exchanges).",
    "lev.realTitle": "REAL PER-COIN LEVERAGE (exchange data)",
    "lev.maxAcross": "Max (all exchanges)",
    "lev.typical": "Typical",
    "lev.venuesShort": "Venues w/ leverage",
    "lev.appliesOnTrade": "Leverage is applied to position sizing when a trade (LONG/SHORT) appears.",

    "density.title": "Order-book density",
    "density.subtitle": "live walls & heatmap",
    "density.none": "No order-book data.",
    "density.mid": "Mid",
    "density.spread": "Spread",
    "density.imbalance": "Imbalance",
    "density.walls": "Walls",
    "density.wallsTitle": "TOP LIQUIDITY WALLS",
    "density.col.side": "Side",
    "density.col.price": "Price",
    "density.col.size": "Size",
    "density.col.notional": "Notional $",
    "density.col.z": "Z",
    "density.bid": "BID",
    "density.ask": "ASK",

    "compare.title": "Cross-exchange comparison",
    "compare.loading": "Loading comparison…",
    "compare.avg": "Avg price",
    "compare.spread": "Spread",
    "compare.buySell": "Buy / Sell",
    "compare.col.exchange": "Exchange",
    "compare.col.last": "Last",
    "compare.col.bid": "Bid",
    "compare.col.ask": "Ask",
    "compare.col.dev": "Δ vs avg",
    "compare.cheapest": "cheapest",
    "compare.priciest": "priciest",
    "compare.unavailable": "Unavailable: {list}",

    "footer":
      "Data via public CCXT endpoints. Walls = order-book levels whose notional size is a statistical outlier (z-score). Leverage is pulled from real exchange perpetual limits. ML predicts the next {h}-candle move (down / flat / up). Not financial advice.",
  },
};

const LangContext = createContext({ lang: "ru", setLang: () => {}, t: (k) => k });

function interpolate(str, vars) {
  if (!vars) return str;
  return str.replace(/\{(\w+)\}/g, (_, k) => (vars[k] != null ? String(vars[k]) : `{${k}}`));
}

export function LangProvider({ children }) {
  const [lang, setLang] = useState(() => localStorage.getItem("lang") || "ru");
  useEffect(() => {
    localStorage.setItem("lang", lang);
    document.documentElement.lang = lang;
  }, [lang]);

  const t = useCallback(
    (key, vars) => {
      const dict = STRINGS[lang] || STRINGS.ru;
      const s = dict[key] ?? STRINGS.ru[key] ?? key;
      return interpolate(s, vars);
    },
    [lang]
  );

  const value = useMemo(() => ({ lang, setLang, t }), [lang, t]);
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export function useT() {
  return useContext(LangContext);
}
