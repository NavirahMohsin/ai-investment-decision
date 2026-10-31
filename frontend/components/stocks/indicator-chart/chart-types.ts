import type { ReactNode } from "react";

export interface ChartDimensions {
  width: number;
  height: number;
}

export interface ChartPadding {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

export interface ChartPoint {
  date: string;
  value: number | null;
}

export interface ChartSeries {
  key: string;
  label: string;
  values: Array<number | null>;
  visible?: boolean;
  color?: string;
  lineStyle?: "solid" | "dashed" | "dotted";
  strokeWidth?: number;
  format?: "number" | "price" | "percent";
}

export interface ChartScale {
  minimum: number;
  maximum: number;
  range: number;
}

export interface ChartSelection {
  index: number;
  date: string;
}

export interface ChartConfiguration {
  dimensions: ChartDimensions;
  padding: ChartPadding;
  dateLabelCount?: number;
  ariaLabel?: string;
  emptyState?: ReactNode;
}

export interface AlignedChartData {
  dates: string[];
  series: ChartSeries[];
}
