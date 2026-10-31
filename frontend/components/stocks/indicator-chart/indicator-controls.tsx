"use client";

import { useState } from "react";
import { Settings2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { FetchStockIndicatorsOptions } from "@/lib/api";

export interface IndicatorVisibility {
  sma: boolean;
  ema: boolean;
  bollinger: boolean;
  rsi: boolean;
  macd: boolean;
  atr: boolean;
}

interface IndicatorControlsProps {
  visibility: IndicatorVisibility;
  onVisibilityChange: (visibility: IndicatorVisibility) => void;
  options: FetchStockIndicatorsOptions;
  onApply: (options: FetchStockIndicatorsOptions) => void;
  disabled?: boolean;
}

const defaults: Required<Omit<FetchStockIndicatorsOptions, "price_field">> = {
  sma_period: 20,
  ema_period: 20,
  rsi_period: 14,
  macd_fast_period: 12,
  macd_slow_period: 26,
  macd_signal_period: 9,
  bollinger_period: 20,
  bollinger_std_dev: 2,
  atr_period: 14,
};

function readPositiveInteger(value: string) {
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
}

function readPositiveNumber(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export function IndicatorControls({
  visibility,
  onVisibilityChange,
  options,
  onApply,
  disabled = false,
}: IndicatorControlsProps) {
  const [draft, setDraft] = useState({ ...defaults, ...options });
  const [validationError, setValidationError] = useState<string | null>(null);

  function updateNumber(key: keyof typeof defaults, value: string) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function apply() {
    const next = {
      sma_period: readPositiveInteger(String(draft.sma_period)),
      ema_period: readPositiveInteger(String(draft.ema_period)),
      rsi_period: readPositiveInteger(String(draft.rsi_period)),
      macd_fast_period: readPositiveInteger(String(draft.macd_fast_period)),
      macd_slow_period: readPositiveInteger(String(draft.macd_slow_period)),
      macd_signal_period: readPositiveInteger(String(draft.macd_signal_period)),
      bollinger_period: readPositiveInteger(String(draft.bollinger_period)),
      bollinger_std_dev: readPositiveNumber(String(draft.bollinger_std_dev)),
      atr_period: readPositiveInteger(String(draft.atr_period)),
    };
    if (
      next.sma_period === null ||
      next.ema_period === null ||
      next.rsi_period === null ||
      next.macd_fast_period === null ||
      next.macd_slow_period === null ||
      next.macd_signal_period === null ||
      next.bollinger_period === null ||
      next.bollinger_std_dev === null ||
      next.atr_period === null
    ) {
      setValidationError("Periods must be positive integers and standard deviation must be a positive number.");
      return;
    }
    if (next.macd_fast_period >= next.macd_slow_period) {
      setValidationError("MACD fast period must be smaller than slow period.");
      return;
    }
    if (!Number.isFinite(next.bollinger_std_dev) || next.bollinger_std_dev <= 0) {
      setValidationError("Bollinger standard deviation must be greater than zero.");
      return;
    }
    setValidationError(null);
    const validatedOptions: FetchStockIndicatorsOptions = {
      sma_period: next.sma_period,
      ema_period: next.ema_period,
      rsi_period: next.rsi_period,
      macd_fast_period: next.macd_fast_period,
      macd_slow_period: next.macd_slow_period,
      macd_signal_period: next.macd_signal_period,
      bollinger_period: next.bollinger_period,
      bollinger_std_dev: next.bollinger_std_dev,
      atr_period: next.atr_period,
    };
    onApply(validatedOptions);
  }

  const toggles: Array<[keyof IndicatorVisibility, string, string]> = [
    ["sma", "SMA", "Price overlay"],
    ["ema", "EMA", "Price overlay"],
    ["bollinger", "Bollinger Bands", "Price overlay"],
    ["rsi", "RSI", "Panel"],
    ["macd", "MACD", "Panel"],
    ["atr", "ATR", "Panel"],
  ];

  return (
    <Card className="border-border/70 bg-card/80 shadow-none">
      <CardHeader className="flex flex-row items-center justify-between gap-3 border-b border-border/60 px-5 py-4 sm:px-6">
        <div>
          <CardTitle className="flex items-center gap-2 text-base"><Settings2 className="size-4 text-cyan-300" /> Technical analysis</CardTitle>
          <p className="mt-1 text-xs text-muted-foreground">Research indicators are calculated from stored historical data.</p>
        </div>
        <Button type="button" size="sm" onClick={apply} disabled={disabled}>Apply settings</Button>
      </CardHeader>
      <CardContent className="space-y-5 p-5 sm:px-6">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {toggles.map(([key, label, kind]) => (
            <label key={key} className="flex cursor-pointer items-center justify-between rounded-lg border border-border/70 bg-background/30 px-3 py-2 text-sm">
              <span><span className="font-medium">{label}</span><span className="ml-2 text-xs text-muted-foreground">{kind}</span></span>
              <input type="checkbox" checked={visibility[key]} onChange={(event) => onVisibilityChange({ ...visibility, [key]: event.target.checked })} disabled={disabled} className="size-4 accent-cyan-300" />
            </label>
          ))}
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {[
            ["sma_period", "SMA period"],
            ["ema_period", "EMA period"],
            ["rsi_period", "RSI period"],
            ["bollinger_period", "Bollinger period"],
            ["atr_period", "ATR period"],
            ["macd_fast_period", "MACD fast"],
            ["macd_slow_period", "MACD slow"],
            ["macd_signal_period", "MACD signal"],
            ["bollinger_std_dev", "Bollinger std dev"],
          ].map(([key, label]) => (
            <label key={key} className="text-xs text-muted-foreground">
              {label}
              <input
                type="number"
                min="0.1"
                step={key === "bollinger_std_dev" ? "0.1" : "1"}
                value={String(draft[key as keyof typeof draft])}
                onChange={(event) => updateNumber(key as keyof typeof defaults, event.target.value)}
                disabled={disabled}
                className="mt-1 h-9 w-full rounded-md border border-input bg-background/60 px-2 text-sm text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
              />
            </label>
          ))}
        </div>
        {validationError && <p className="text-sm text-rose-300">{validationError}</p>}
      </CardContent>
    </Card>
  );
}
