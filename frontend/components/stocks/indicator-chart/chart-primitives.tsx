"use client";

import type { ReactNode } from "react";
import { getPlotDimensions, getValueBounds, getXCoordinate, getYCoordinate, getTicks } from "./chart-scales";
import type { ChartDimensions, ChartPadding, ChartScale, ChartSeries } from "./chart-types";

const defaultColors = ["#67e8f9", "#60a5fa", "#a78bfa", "#34d399", "#fbbf24"];

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

function formatValue(value: number) {
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(value);
}

export function GridLines({
  scale,
  dimensions,
  padding,
  tickCount = 3,
}: {
  scale: ChartScale;
  dimensions: ChartDimensions;
  padding: ChartPadding;
  tickCount?: number;
}) {
  const plot = getPlotDimensions(dimensions, padding);
  return (
    <>
      {getTicks(scale, tickCount).map((value) => {
        const y = getYCoordinate(value, scale, dimensions, padding);
        return y === null ? null : (
          <line key={value} x1={padding.left} x2={dimensions.width - padding.right} y1={y} y2={y} stroke="currentColor" className="text-border/60" strokeDasharray="3 5" />
        );
      })}
      <line x1={padding.left} x2={dimensions.width - padding.right} y1={dimensions.height - padding.bottom} y2={dimensions.height - padding.bottom} stroke="currentColor" className="text-border" />
      <rect x={padding.left} y={padding.top} width={plot.width} height={plot.height} fill="none" pointerEvents="none" />
    </>
  );
}

export function YAxisLabels({
  scale,
  dimensions,
  padding,
  tickCount = 3,
  format = formatValue,
}: {
  scale: ChartScale;
  dimensions: ChartDimensions;
  padding: ChartPadding;
  tickCount?: number;
  format?: (value: number) => string;
}) {
  return (
    <>
      {getTicks(scale, tickCount).map((value) => {
        const y = getYCoordinate(value, scale, dimensions, padding);
        return y === null ? null : (
          <text key={value} x={padding.left - 8} y={y + 4} textAnchor="end" className="fill-muted-foreground text-[11px]">
            {format(value)}
          </text>
        );
      })}
    </>
  );
}

export function XAxisLabels({
  dates,
  dimensions,
  padding,
  count = 3,
}: {
  dates: readonly string[];
  dimensions: ChartDimensions;
  padding: ChartPadding;
  count?: number;
}) {
  const indexes = Array.from({ length: Math.min(Math.max(count, 1), dates.length) }, (_, index) =>
    dates.length <= 1 ? 0 : Math.round((index / Math.max(Math.min(count, dates.length) - 1, 1)) * (dates.length - 1)),
  );
  return (
    <>
      {indexes.map((index) => (
        <text key={`${dates[index]}-${index}`} x={getXCoordinate(index, dates.length, dimensions, padding)} y={dimensions.height - 10} textAnchor="middle" className="fill-muted-foreground text-[11px]">
          {formatDate(dates[index])}
        </text>
      ))}
    </>
  );
}

function lineSegments(series: ChartSeries, dates: readonly string[], dimensions: ChartDimensions, padding: ChartPadding, scale: ChartScale) {
  const segments: string[] = [];
  let segment: string[] = [];
  series.values.forEach((value, index) => {
    const y = getYCoordinate(value, scale, dimensions, padding);
    if (y === null) {
      if (segment.length > 0) segments.push(segment.join(" "));
      segment = [];
      return;
    }
    segment.push(`${getXCoordinate(index, dates.length, dimensions, padding)},${y}`);
  });
  if (segment.length > 0) segments.push(segment.join(" "));
  return segments;
}

export function SeriesPolylines({
  dates,
  series,
  dimensions,
  padding,
  scale,
}: {
  dates: readonly string[];
  series: readonly ChartSeries[];
  dimensions: ChartDimensions;
  padding: ChartPadding;
  scale: ChartScale;
}) {
  return (
    <>
      {series.filter((item) => item.visible !== false).flatMap((item, seriesIndex) =>
        lineSegments(item, dates, dimensions, padding, scale).map((points, segmentIndex) => (
          <polyline
            key={`${item.key}-${segmentIndex}`}
            points={points}
            fill="none"
            stroke={item.color ?? defaultColors[seriesIndex % defaultColors.length]}
            strokeWidth={item.strokeWidth ?? 2}
            strokeDasharray={item.lineStyle === "dashed" ? "7 5" : item.lineStyle === "dotted" ? "2 4" : undefined}
            vectorEffect="non-scaling-stroke"
          />
        )),
      )}
    </>
  );
}

export function ReferenceLine({
  value,
  scale,
  dimensions,
  padding,
  label,
  color = "currentColor",
}: {
  value: number;
  scale: ChartScale;
  dimensions: ChartDimensions;
  padding: ChartPadding;
  label?: string;
  color?: string;
}) {
  const y = getYCoordinate(value, scale, dimensions, padding);
  if (y === null) return null;
  return (
    <g>
      <line x1={padding.left} x2={dimensions.width - padding.right} y1={y} y2={y} stroke={color} strokeDasharray="5 5" vectorEffect="non-scaling-stroke" />
      {label && <text x={dimensions.width - padding.right - 4} y={y - 4} textAnchor="end" fill={color} className="text-[11px]">{label}</text>}
    </g>
  );
}

export function HistogramBars({
  dates,
  values,
  dimensions,
  padding,
  scale = getValueBounds(values),
  positiveColor = "#34d399",
  negativeColor = "#fb7185",
}: {
  dates: readonly string[];
  values: readonly (number | null)[];
  dimensions: ChartDimensions;
  padding: ChartPadding;
  scale?: ChartScale;
  positiveColor?: string;
  negativeColor?: string;
}) {
  const zero = getYCoordinate(0, scale, dimensions, padding) ?? dimensions.height - padding.bottom;
  const width = Math.max(1, getPlotDimensions(dimensions, padding).width / Math.max(dates.length, 1) - 1);
  return (
    <>
      {values.map((value, index) => {
        const y = getYCoordinate(value, scale, dimensions, padding);
        if (value === null || y === null) return null;
        const top = Math.min(y, zero);
        return <rect key={dates[index] ?? index} x={getXCoordinate(index, dates.length, dimensions, padding) - width / 2} y={top} width={width} height={Math.max(1, Math.abs(zero - y))} fill={value >= 0 ? positiveColor : negativeColor} opacity="0.7" rx="1" />;
      })}
    </>
  );
}

export function ChartEmptyState({ message }: { message: ReactNode }) {
  return <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-border/70 bg-background/30 px-6 text-center text-sm text-muted-foreground">{message}</div>;
}
