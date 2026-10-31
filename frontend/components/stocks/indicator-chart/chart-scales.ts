import type { ChartDimensions, ChartPadding, ChartScale } from "./chart-types";

export interface PlotDimensions {
  width: number;
  height: number;
}

export function getPlotDimensions(
  dimensions: ChartDimensions,
  padding: ChartPadding,
): PlotDimensions {
  return {
    width: Math.max(0, dimensions.width - padding.left - padding.right),
    height: Math.max(0, dimensions.height - padding.top - padding.bottom),
  };
}

export function getXCoordinate(
  index: number,
  pointCount: number,
  dimensions: ChartDimensions,
  padding: ChartPadding,
): number {
  const plot = getPlotDimensions(dimensions, padding);
  return padding.left + (index / Math.max(pointCount - 1, 1)) * plot.width;
}

export function getValueBounds(values: readonly (number | null)[]): ChartScale {
  const finiteValues = values.filter(
    (value): value is number => value !== null && Number.isFinite(value),
  );
  if (finiteValues.length === 0) {
    return { minimum: 0, maximum: 1, range: 1 };
  }

  const minimum = Math.min(...finiteValues);
  const maximum = Math.max(...finiteValues);
  if (minimum !== maximum) {
    return { minimum, maximum, range: maximum - minimum };
  }

  const padding = Math.max(Math.abs(minimum) * 0.02, 1);
  return {
    minimum: minimum - padding,
    maximum: maximum + padding,
    range: padding * 2,
  };
}

export function getYCoordinate(
  value: number | null,
  scale: ChartScale,
  dimensions: ChartDimensions,
  padding: ChartPadding,
): number | null {
  if (value === null || !Number.isFinite(value) || scale.range <= 0) {
    return null;
  }
  const plot = getPlotDimensions(dimensions, padding);
  const coordinate = padding.top + (1 - (value - scale.minimum) / scale.range) * plot.height;
  return Number.isFinite(coordinate) ? coordinate : null;
}

export function getTicks(scale: ChartScale, count = 3): number[] {
  const safeCount = Math.max(2, Math.floor(count));
  return Array.from({ length: safeCount }, (_, index) => {
    const fraction = index / (safeCount - 1);
    return scale.maximum - fraction * scale.range;
  });
}
