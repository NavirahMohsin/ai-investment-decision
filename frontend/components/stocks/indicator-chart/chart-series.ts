import type { AlignedChartData, ChartSeries } from "./chart-types";

export interface DatedValue {
  trading_date: string;
  value: number | null;
}

export interface DatedSeries extends Array<DatedValue> {
  key?: string;
  label?: string;
}

function isFiniteOrNull(value: number | null): value is number | null {
  return value === null || Number.isFinite(value);
}

export function buildTradingDates(series: readonly DatedValue[][]): string[] {
  return Array.from(
    new Set(
      series
        .flat()
        .map((point) => point.trading_date)
        .filter((date): date is string => typeof date === "string"),
    ),
  ).sort();
}

export function alignSeries(
  dates: readonly string[],
  series: readonly DatedValue[][],
): Array<number | null>[] {
  return series.map((points) => {
    const valuesByDate = new Map(
      points.map((point) => [
        point.trading_date,
        isFiniteOrNull(point.value) ? point.value : null,
      ]),
    );
    return dates.map((date) => valuesByDate.get(date) ?? null);
  });
}

export function alignChartSeries(
  series: readonly DatedSeries[],
): AlignedChartData {
  const dates = buildTradingDates(series);
  const values = alignSeries(dates, series);
  return {
    dates,
    series: series.map((item, index): ChartSeries => ({
      key: item.key ?? `series-${index}`,
      label: item.label ?? `Series ${index + 1}`,
      values: values[index],
    })),
  };
}
