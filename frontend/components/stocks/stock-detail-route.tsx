"use client";

import { useParams } from "next/navigation";
import { StockDetail } from "@/components/stocks/stock-detail";

export function StockDetailRoute() {
  const params = useParams<{ symbol: string }>();
  const symbol = decodeURIComponent(params.symbol).toUpperCase();
  return <StockDetail symbol={symbol} />;
}
