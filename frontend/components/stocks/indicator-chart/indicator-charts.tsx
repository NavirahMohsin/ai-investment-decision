"use client";

import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { HistoricalPriceResponse, TechnicalIndicatorRecord } from "@/lib/api";
import { alignSeries, buildTradingDates } from "./chart-series";
import { getPlotDimensions, getValueBounds, getXCoordinate, getYCoordinate, getTicks } from "./chart-scales";
import type { ChartScale } from "./chart-types";
import { ChartTooltip, getTooltipValues } from "./chart-tooltip";
import type { IndicatorVisibility } from "./indicator-controls";

const dimensions = { width: 900, height: 280 };
const padding = { top: 20, right: 20, bottom: 38, left: 62 };
const colors = {
  close: "#67e8f9",
  sma: "#60a5fa",
  ema: "#a78bfa",
  bollinger: "#fbbf24",
  rsi: "#34d399",
  macd: "#60a5fa",
  signal: "#fbbf24",
  histogramPositive: "#34d399",
  histogramNegative: "#fb7185",
  atr: "#c084fc",
};

interface PanelSeries {
  key: string;
  label: string;
  values: Array<number | null>;
  color: string;
  dashed?: boolean;
  format?: "number" | "price" | "percent";
}

interface IndicatorChartsProps {
  history: HistoricalPriceResponse;
  records: TechnicalIndicatorRecord[];
  visibility: IndicatorVisibility;
  selectedIndex: number | null;
  onSelectionChange: (index: number) => void;
}

function formatValue(value: number) {
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(value);
}

function formatPrice(value: number) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(value);
}

function PanelLegend({ items }: { items: Array<[string, string]> }) {
  return <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">{items.map(([label, color]) => <span key={label} className="inline-flex items-center gap-1.5"><span className="size-2 rounded-full" style={{ backgroundColor: color }} />{label}</span>)}</div>;
}

function PanelFrame({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="border-border/70 bg-card/80 shadow-none">
      <CardHeader className="border-b border-border/60 px-5 py-4 sm:px-6">
        <CardTitle className="text-base">{title}</CardTitle>
        <p className="text-xs text-muted-foreground">{description}</p>
      </CardHeader>
      <CardContent className="p-4 sm:p-6">{children}</CardContent>
    </Card>
  );
}

function Axis({
  scale,
  format = formatValue,
  referenceValues = [],
}: {
  scale: ChartScale;
  format?: (value: number) => string;
  referenceValues?: Array<[number, string]>;
}) {
  const plot = getPlotDimensions(dimensions, padding);
  return (
    <>
      {getTicks(scale, 3).map((value) => {
        const y = getYCoordinate(value, scale, dimensions, padding);
        return y === null ? null : <g key={value}><line x1={padding.left} x2={dimensions.width - padding.right} y1={y} y2={y} stroke="currentColor" className="text-border/60" strokeDasharray="3 5" /><text x={padding.left - 8} y={y + 4} textAnchor="end" className="fill-muted-foreground text-[11px]">{format(value)}</text></g>;
      })}
      {referenceValues.map(([value, label]) => {
        const y = getYCoordinate(value, scale, dimensions, padding);
        return y === null ? null : <g key={label}><line x1={padding.left} x2={dimensions.width - padding.right} y1={y} y2={y} stroke="currentColor" className="text-muted-foreground" strokeDasharray="5 5" /><text x={dimensions.width - padding.right - 4} y={y - 4} textAnchor="end" className="fill-muted-foreground text-[11px]">{label}</text></g>;
      })}
      <line x1={padding.left} x2={dimensions.width - padding.right} y1={dimensions.height - padding.bottom} y2={dimensions.height - padding.bottom} stroke="currentColor" className="text-border" />
      <rect x={padding.left} y={padding.top} width={plot.width} height={plot.height} fill="none" pointerEvents="none" />
    </>
  );
}

function DateLabels({ dates }: { dates: string[] }) {
  const indexes = dates.length === 0 ? [] : [0, Math.floor((dates.length - 1) / 2), dates.length - 1];
  return <>{indexes.map((index) => <text key={`${dates[index]}-${index}`} x={getXCoordinate(index, dates.length, dimensions, padding)} y={dimensions.height - 10} textAnchor="middle" className="fill-muted-foreground text-[11px]">{new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(`${dates[index]}T00:00:00Z`))}</text>)}</>;
}

function lineSegments(values: Array<number | null>, dates: string[], scale: ChartScale) {
  const segments: string[] = [];
  let segment: string[] = [];
  values.forEach((value, index) => {
    const y = getYCoordinate(value, scale, dimensions, padding);
    if (y === null) {
      if (segment.length) segments.push(segment.join(" "));
      segment = [];
      return;
    }
    segment.push(`${getXCoordinate(index, dates.length, dimensions, padding)},${y}`);
  });
  if (segment.length) segments.push(segment.join(" "));
  return segments;
}

function Lines({
  series,
  dates,
  scale,
}: {
  series: Array<{ key: string; label: string; values: Array<number | null>; color: string; dashed?: boolean }>;
  dates: string[];
  scale: ChartScale;
}) {
  return <>{series.flatMap((item) => lineSegments(item.values, dates, scale).map((points, index) => <polyline key={`${item.key}-${index}`} points={points} fill="none" stroke={item.color} strokeWidth="2" strokeDasharray={item.dashed ? "7 5" : undefined} vectorEffect="non-scaling-stroke" />))}</>;
}

function SelectionOverlay({
  dates,
  selectedIndex,
  onSelectionChange,
  values,
  series,
  scale,
  price = false,
}: {
  dates: string[];
  selectedIndex: number;
  onSelectionChange: (index: number) => void;
  values: ReturnType<typeof getTooltipValues>;
  series: Array<{ key: string; label: string; values: Array<number | null>; color: string; format?: "number" | "price" | "percent" }>;
  scale: ChartScale;
  price?: boolean;
}) {
  const x = getXCoordinate(selectedIndex, dates.length, dimensions, padding);
  const selectedValue = series.find((item) => item.values[selectedIndex] !== null)?.values[selectedIndex] ?? null;
  const y = getYCoordinate(selectedValue, scale, dimensions, padding) ?? padding.top;
  const selection = { index: selectedIndex, date: dates[selectedIndex] };
  return (
    <>
      <line x1={x} x2={x} y1={padding.top} y2={dimensions.height - padding.bottom} stroke="currentColor" className="text-muted-foreground/60" strokeDasharray="3 4" vectorEffect="non-scaling-stroke" />
      <circle cx={x} cy={y} r="5" className="fill-cyan-300 stroke-background" strokeWidth="2" />
      <ChartTooltip selection={selection} values={values} dimensions={dimensions} x={x} y={y} />
      <text x={x} y={dimensions.height - 2} textAnchor="middle" className="fill-muted-foreground text-[10px]">{selection.date}</text>
      {dates.map((date, index) => <rect key={date} x={getXCoordinate(index, dates.length, dimensions, padding) - Math.max(12, getPlotDimensions(dimensions, padding).width / Math.max(dates.length, 1) / 2)} y={padding.top} width={Math.max(24, getPlotDimensions(dimensions, padding).width / Math.max(dates.length, 1))} height={dimensions.height - padding.top - padding.bottom} fill="transparent" tabIndex={index === selectedIndex ? 0 : -1} aria-label={`${date}${price ? " price" : " indicator"} chart point`} onMouseEnter={() => onSelectionChange(index)} onFocus={() => onSelectionChange(index)} />)}
    </>
  );
}

function useAlignedData(history: HistoricalPriceResponse, records: TechnicalIndicatorRecord[]) {
  return useMemo(() => {
    const dated = records.map((record) => ({ trading_date: record.trading_date, value: record.close }));
    const historyDated = history.records.map((record) => ({ trading_date: record.trading_date, value: Number(record.close) }));
    const dates = buildTradingDates([historyDated, dated]);
    const aligned = alignSeries(dates, [
      historyDated,
      records.map((record) => ({ trading_date: record.trading_date, value: record.sma })),
      records.map((record) => ({ trading_date: record.trading_date, value: record.ema })),
      records.map((record) => ({ trading_date: record.trading_date, value: record.bollinger_middle })),
      records.map((record) => ({ trading_date: record.trading_date, value: record.bollinger_upper })),
      records.map((record) => ({ trading_date: record.trading_date, value: record.bollinger_lower })),
      records.map((record) => ({ trading_date: record.trading_date, value: record.rsi })),
      records.map((record) => ({ trading_date: record.trading_date, value: record.macd })),
      records.map((record) => ({ trading_date: record.trading_date, value: record.macd_signal })),
      records.map((record) => ({ trading_date: record.trading_date, value: record.macd_histogram })),
      records.map((record) => ({ trading_date: record.trading_date, value: record.atr })),
    ]);
    return { dates, values: aligned };
  }, [history, records]);
}

export function IndicatorCharts({ history, records, visibility, selectedIndex, onSelectionChange }: IndicatorChartsProps) {
  const { dates, values } = useAlignedData(history, records);
  const close = values[0];
  const priceSeries = [
    { key: "close", label: "Close", values: close, color: colors.close, format: "price" as const },
    ...(visibility.sma ? [{ key: "sma", label: "SMA", values: values[1], color: colors.sma, format: "price" as const }] : []),
    ...(visibility.ema ? [{ key: "ema", label: "EMA", values: values[2], color: colors.ema, format: "price" as const }] : []),
    ...(visibility.bollinger ? [
      { key: "bollinger_middle", label: "Bollinger middle", values: values[3], color: colors.bollinger, format: "price" as const },
      { key: "bollinger_upper", label: "Bollinger upper", values: values[4], color: colors.bollinger, dashed: true, format: "price" as const },
      { key: "bollinger_lower", label: "Bollinger lower", values: values[5], color: colors.bollinger, dashed: true, format: "price" as const },
    ] : []),
  ];
  const priceScale = getValueBounds(priceSeries.flatMap((item) => item.values));
  const rsiSeries = [{ key: "rsi", label: "RSI", values: values[6], color: colors.rsi, format: "number" as const }];
  const macdSeries = [{ key: "macd", label: "MACD", values: values[7], color: colors.macd }, { key: "signal", label: "Signal", values: values[8], color: colors.signal, dashed: true }];
  const macdScale = getValueBounds([...values[7], ...values[8], ...values[9]]);
  const atrSeries = [{ key: "atr", label: "ATR", values: values[10], color: colors.atr }];
  const effectiveSelection = selectedIndex === null ? Math.max(dates.length - 1, 0) : selectedIndex;
  const indicatorRecord = records.find((record) => record.trading_date === dates[effectiveSelection]);
  const tooltip = (items: Array<{ key: string; label: string; values: Array<number | null>; color: string; format?: "number" | "price" | "percent" }>) => getTooltipValues(items, effectiveSelection);

  function renderPanel(title: string, description: string, series: PanelSeries[], scale: ChartScale, legend: Array<[string, string]>, references: Array<[number, string]> = [], format = formatValue, histogram?: Array<number | null>) {
    return <PanelFrame title={title} description={description}><PanelLegend items={legend} /><div className="mt-3"><svg viewBox={`0 0 ${dimensions.width} ${dimensions.height}`} className="h-auto w-full" preserveAspectRatio="none"><Axis scale={scale} format={format} referenceValues={references} /><Lines series={series} dates={dates} scale={scale} />{histogram && histogram.map((value, index) => { const y = getYCoordinate(value, scale, dimensions, padding); const zero = getYCoordinate(0, scale, dimensions, padding); if (y === null || zero === null || value === null) return null; const width = Math.max(1, getPlotDimensions(dimensions, padding).width / Math.max(dates.length, 1) - 1); return <rect key={dates[index]} x={getXCoordinate(index, dates.length, dimensions, padding) - width / 2} y={Math.min(y, zero)} width={width} height={Math.max(1, Math.abs(zero - y))} fill={value >= 0 ? colors.histogramPositive : colors.histogramNegative} opacity="0.7" />; })}<DateLabels dates={dates} />{dates.length > 0 && <SelectionOverlay dates={dates} selectedIndex={effectiveSelection} onSelectionChange={onSelectionChange} values={tooltip(series)} series={series} scale={scale} />}</svg></div></PanelFrame>;
  }

  if (dates.length === 0) return <Card className="border-border/70 bg-card/80 shadow-none"><CardContent className="p-6 text-center text-sm text-muted-foreground">No technical-indicator data is available for this range.</CardContent></Card>;
  return (
    <div className="space-y-5">
      {renderPanel("Price with overlays", "Daily close with optional moving averages and Bollinger Bands.", priceSeries, priceScale, [["Close", colors.close], ...(visibility.sma ? [["SMA", colors.sma] as [string, string]] : []), ...(visibility.ema ? [["EMA", colors.ema] as [string, string]] : []), ...(visibility.bollinger ? [["Bollinger Bands", colors.bollinger] as [string, string]] : [])], [], formatPrice)}
      {visibility.rsi && renderPanel("Relative Strength Index", "RSI above 70 is commonly considered overbought and below 30 oversold; neither level is a guaranteed signal.", rsiSeries, { minimum: 0, maximum: 100, range: 100 }, [["RSI", colors.rsi]], [[70, "70"], [30, "30"]])}
      {visibility.macd && renderPanel("MACD", "Momentum view with MACD, signal line, and histogram.", macdSeries, macdScale, [["MACD", colors.macd], ["Signal", colors.signal], ["Histogram", colors.histogramPositive]], [[0, "0"]], formatValue, values[9])}
      {visibility.atr && renderPanel("Average True Range", "ATR measures volatility, not price direction.", atrSeries, getValueBounds(values[10]), [["ATR", colors.atr]])}
      <p className="text-xs text-muted-foreground">Selected date: {dates[effectiveSelection]}{indicatorRecord?.rsi === null ? " · Some indicator values are unavailable during warm-up." : ""}</p>
    </div>
  );
}
