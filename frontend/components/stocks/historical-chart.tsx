"use client";

import { useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { HistoricalPriceRecord } from "@/lib/api";

type ChartPoint = { date: string; value: number };

const chartWidth = 900;
const chartHeight = 280;
const chartPadding = { top: 20, right: 20, bottom: 38, left: 58 };

function valueOf(value: string | number | null) {
  return value === null ? null : Number(value);
}

function formatPrice(value: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(value);
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

function ChartEmptyState({ message }: { message: string }) {
  return (
    <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-border/70 bg-background/30 px-6 text-center text-sm text-muted-foreground">
      {message}
    </div>
  );
}

export function ClosingPriceChart({ records }: { records: HistoricalPriceRecord[] }) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const points = useMemo<ChartPoint[]>(
    () =>
      records.flatMap((record) => {
        const value = valueOf(record.close);
        return value !== null && Number.isFinite(value)
          ? [{ date: record.trading_date, value }]
          : [];
      }),
    [records],
  );

  if (points.length === 0) {
    return <ChartEmptyState message="No historical closing-price data is available for this range." />;
  }

  const values = points.map((point) => point.value);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const range = maximum - minimum || Math.max(maximum * 0.02, 1);
  const plotWidth = chartWidth - chartPadding.left - chartPadding.right;
  const plotHeight = chartHeight - chartPadding.top - chartPadding.bottom;
  const coordinates = points.map((point, index) => ({
    x: chartPadding.left + (index / Math.max(points.length - 1, 1)) * plotWidth,
    y: chartPadding.top + (1 - (point.value - minimum) / range) * plotHeight,
  }));
  const line = coordinates.map((point) => `${point.x},${point.y}`).join(" ");
  const selectedIndex = hoveredIndex ?? points.length - 1;
  const selectedPoint = points[selectedIndex];
  const selectedCoordinate = coordinates[selectedIndex];
  const labelIndexes = [0, Math.floor((points.length - 1) / 2), points.length - 1];

  return (
    <Card className="border-border/70 bg-card/80 shadow-none">
      <CardHeader className="border-b border-border/60 px-5 py-5 sm:px-6">
        <CardTitle className="text-base">Historical closing price</CardTitle>
        <p className="text-xs text-muted-foreground">Daily close in Indian rupees · Hover or focus points for exact values</p>
      </CardHeader>
      <CardContent className="p-4 sm:p-6">
        <div className="sr-only" aria-live="polite">
          Closing price on {formatDate(selectedPoint.date)}: {formatPrice(selectedPoint.value)}
        </div>
        <div className="overflow-hidden" role="img" aria-label="Interactive historical closing price chart">
          <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="h-auto w-full" preserveAspectRatio="none">
            {[0, 0.5, 1].map((fraction) => {
              const y = chartPadding.top + fraction * plotHeight;
              const label = maximum - fraction * range;
              return (
                <g key={fraction}>
                  <line x1={chartPadding.left} x2={chartWidth - chartPadding.right} y1={y} y2={y} stroke="currentColor" className="text-border/60" strokeDasharray="3 5" />
                  <text x={chartPadding.left - 8} y={y + 4} textAnchor="end" className="fill-muted-foreground text-[11px]">{formatPrice(label)}</text>
                </g>
              );
            })}
            <polyline points={line} fill="none" stroke="currentColor" strokeWidth="2.5" className="text-cyan-300" vectorEffect="non-scaling-stroke" />
            {coordinates.map((point, index) => (
              <circle
                key={points[index].date}
                cx={point.x}
                cy={point.y}
                r={index === selectedIndex ? 5 : 2}
                className="cursor-crosshair fill-cyan-300 stroke-background"
                strokeWidth="2"
                tabIndex={0}
                aria-label={`${formatDate(points[index].date)}: ${formatPrice(points[index].value)}`}
                onMouseEnter={() => setHoveredIndex(index)}
                onFocus={() => setHoveredIndex(index)}
                onMouseLeave={() => setHoveredIndex(null)}
              />
            ))}
            {labelIndexes.map((index) => (
              <text key={points[index].date} x={coordinates[index].x} y={chartHeight - 10} textAnchor="middle" className="fill-muted-foreground text-[11px]">{formatDate(points[index].date)}</text>
            ))}
            <g pointerEvents="none">
              <rect x={Math.min(Math.max(selectedCoordinate.x - 78, chartPadding.left), chartWidth - 176)} y={Math.max(selectedCoordinate.y - 48, 4)} width="156" height="34" rx="6" className="fill-popover stroke-border" />
              <text x={Math.min(Math.max(selectedCoordinate.x, chartPadding.left + 78), chartWidth - 98)} y={Math.max(selectedCoordinate.y - 28, 26)} textAnchor="middle" className="fill-popover-foreground text-[11px]">{formatDate(selectedPoint.date)}</text>
              <text x={Math.min(Math.max(selectedCoordinate.x, chartPadding.left + 78), chartWidth - 98)} y={Math.max(selectedCoordinate.y - 14, 40)} textAnchor="middle" className="fill-cyan-300 text-[11px]">{formatPrice(selectedPoint.value)}</text>
            </g>
          </svg>
        </div>
        <div className="mt-2 text-center text-[11px] text-muted-foreground">Trading date (UTC)</div>
      </CardContent>
    </Card>
  );
}

export function VolumeChart({ records }: { records: HistoricalPriceRecord[] }) {
  const points = records.flatMap((record) => Number.isFinite(record.volume) && record.volume >= 0 ? [{ date: record.trading_date, value: record.volume }] : []);
  if (points.length === 0) {
    return <ChartEmptyState message="No trading-volume data is available for this range." />;
  }
  const maximum = Math.max(...points.map((point) => point.value), 1);
  const barWidth = Math.max(1, (chartWidth - chartPadding.left - chartPadding.right) / points.length - 1);
  return (
    <Card className="border-border/70 bg-card/80 shadow-none">
      <CardHeader className="border-b border-border/60 px-5 py-5 sm:px-6">
        <CardTitle className="text-base">Trading volume</CardTitle>
        <p className="text-xs text-muted-foreground">Daily reported volume</p>
      </CardHeader>
      <CardContent className="p-4 sm:p-6">
        <div className="overflow-hidden" role="img" aria-label="Historical daily trading volume chart">
          <svg viewBox={`0 0 ${chartWidth} 180`} className="h-auto w-full" preserveAspectRatio="none">
            <line x1={chartPadding.left} x2={chartWidth - chartPadding.right} y1="150" y2="150" stroke="currentColor" className="text-border" />
            {points.map((point, index) => (
              <rect key={point.date} x={chartPadding.left + index * ((chartWidth - chartPadding.left - chartPadding.right) / points.length)} y={150 - (point.value / maximum) * 125} width={barWidth} height={(point.value / maximum) * 125} className="fill-primary/60 hover:fill-cyan-300" rx="1">
                <title>{`${formatDate(point.date)}: ${point.value.toLocaleString("en-IN")}`}</title>
              </rect>
            ))}
          </svg>
        </div>
        <div className="mt-2 text-center text-[11px] text-muted-foreground">Trading date (UTC)</div>
      </CardContent>
    </Card>
  );
}
