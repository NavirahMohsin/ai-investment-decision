"use client";

import type { ChartSelection, ChartSeries } from "./chart-types";

export interface TooltipValue {
  key: string;
  label: string;
  value: number;
  format?: "number" | "price" | "percent";
}

export function getChartSelection(
  dates: readonly string[],
  index: number,
): ChartSelection | null {
  const safeIndex = Math.max(0, Math.min(index, dates.length - 1));
  const date = dates[safeIndex];
  return date === undefined ? null : { index: safeIndex, date };
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

function formatValue(value: number, format: TooltipValue["format"] = "number") {
  if (format === "price") {
    return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(value);
  }
  return `${new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(value)}${format === "percent" ? "%" : ""}`;
}

export function getTooltipValues(series: readonly ChartSeries[], index: number): TooltipValue[] {
  return series.flatMap((item) => {
    const value = item.values[index] ?? null;
    return value !== null && Number.isFinite(value)
      ? [{ key: item.key, label: item.label, value, format: item.format }]
      : [];
  });
}

export function ChartTooltip({
  selection,
  values,
  dimensions,
  x,
  y,
}: {
  selection: ChartSelection;
  values: readonly TooltipValue[];
  dimensions: { width: number; height: number };
  x: number;
  y: number;
}) {
  const width = 190;
  const height = 28 + Math.max(values.length, 1) * 18;
  const left = Math.min(Math.max(x - width / 2, 4), dimensions.width - width - 4);
  const top = Math.min(Math.max(y - height - 10, 4), dimensions.height - height - 4);
  return (
    <g pointerEvents="none">
      <rect x={left} y={top} width={width} height={height} rx="6" className="fill-popover stroke-border" />
      <text x={left + 10} y={top + 17} className="fill-popover-foreground text-[11px]">{formatDate(selection.date)}</text>
      {values.map((item, index) => (
        <text key={item.key} x={left + 10} y={top + 35 + index * 18} className="fill-muted-foreground text-[11px]">
          {item.label}: <tspan className="fill-cyan-300">{formatValue(item.value, item.format)}</tspan>
        </text>
      ))}
    </g>
  );
}

export function SelectionSummary({
  selection,
  values,
}: {
  selection: ChartSelection;
  values: readonly TooltipValue[];
}) {
  return (
    <div className="sr-only" aria-live="polite">
      {formatDate(selection.date)}. {values.length > 0 ? values.map((item) => `${item.label}: ${formatValue(item.value, item.format)}`).join(", ") : "No values available."}
    </div>
  );
}
