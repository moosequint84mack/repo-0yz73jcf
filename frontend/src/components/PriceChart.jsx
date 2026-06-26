import { useEffect, useRef } from "react";
import { createChart, CrosshairMode } from "lightweight-charts";

// Candlestick chart with volume and horizontal lines for detected liquidity walls.
export default function PriceChart({ candles, walls, support, resistance }) {
  const hostRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  const priceLinesRef = useRef([]);

  useEffect(() => {
    const chart = createChart(hostRef.current, {
      layout: { background: { color: "#131826" }, textColor: "#8b93a7" },
      grid: {
        vertLines: { color: "rgba(35,42,61,0.6)" },
        horzLines: { color: "rgba(35,42,61,0.6)" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#232a3d" },
      timeScale: { borderColor: "#232a3d", timeVisible: true, secondsVisible: false },
      autoSize: true,
    });
    const candleSeries = chart.addCandlestickSeries({
      upColor: "#16c784",
      downColor: "#ea3943",
      borderUpColor: "#16c784",
      borderDownColor: "#ea3943",
      wickUpColor: "#16c784",
      wickDownColor: "#ea3943",
    });
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });
    chart.priceScale("vol").applyOptions({
      scaleMargins: { top: 0.82, bottom: 0 },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;
    return () => chart.remove();
  }, []);

  useEffect(() => {
    if (!candleSeriesRef.current || !candles?.length) return;
    candleSeriesRef.current.setData(
      candles.map((c) => ({
        time: c.time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );
    volumeSeriesRef.current.setData(
      candles.map((c) => ({
        time: c.time,
        value: c.volume,
        color: c.close >= c.open ? "rgba(22,199,132,0.4)" : "rgba(234,57,67,0.4)",
      }))
    );
    chartRef.current.timeScale().fitContent();
  }, [candles]);

  // Draw liquidity walls as price lines on the candle series.
  useEffect(() => {
    const series = candleSeriesRef.current;
    if (!series) return;
    priceLinesRef.current.forEach((l) => series.removePriceLine(l));
    priceLinesRef.current = [];

    const add = (level, color, title) => {
      if (!level) return;
      const line = series.createPriceLine({
        price: level.price,
        color,
        lineWidth: 2,
        lineStyle: 2,
        axisLabelVisible: true,
        title,
      });
      priceLinesRef.current.push(line);
    };

    add(support, "#16c784", "SUP");
    add(resistance, "#ea3943", "RES");
    (walls || []).slice(0, 8).forEach((w) => {
      add(
        w,
        w.side === "bid" ? "rgba(22,199,132,0.45)" : "rgba(234,57,67,0.45)",
        `${w.side === "bid" ? "B" : "A"} z${w.zscore.toFixed(1)}`
      );
    });
  }, [walls, support, resistance]);

  return <div className="chart-host" ref={hostRef} />;
}
