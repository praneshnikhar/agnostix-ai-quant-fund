"use client";

import { useEffect, useRef } from "react";
import {
  ColorType,
  createChart,
  type IChartApi,
  type UTCTimestamp,
} from "lightweight-charts";
import type { Bar } from "@/lib/markets-api";

interface Props {
  bars: Bar[];
  height?: number;
}

/** Candlestick + volume chart over normalized internal Bar data. */
export function CandleChart({ bars, height = 320 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8b8f98",
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.04)" },
        horzLines: { color: "rgba(255,255,255,0.04)" },
      },
      timeScale: { timeVisible: true, borderColor: "#2a2d34" },
      rightPriceScale: { borderColor: "#2a2d34" },
      crosshair: { mode: 0 },
    });

    const candles = chart.addCandlestickSeries({
      upColor: "#26a69a",
      downColor: "#ef5350",
      wickUpColor: "#26a69a",
      wickDownColor: "#ef5350",
      borderVisible: false,
    });
    candles.setData(
      bars.map((b) => ({
        time: Math.floor(new Date(b.event_time).getTime() / 1000) as UTCTimestamp,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      }))
    );

    const volume = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
    volume.setData(
      bars.map((b) => ({
        time: Math.floor(new Date(b.event_time).getTime() / 1000) as UTCTimestamp,
        value: b.volume,
        color: b.close >= b.open ? "rgba(38,166,154,0.4)" : "rgba(239,83,80,0.4)",
      }))
    );

    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [bars, height]);

  return <div ref={containerRef} className="w-full" />;
}