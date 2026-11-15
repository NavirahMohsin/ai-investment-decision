"use client";

import { useEffect, useState } from "react";
import { MoreHorizontal, Star, Loader2, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  fetchWatchlists,
  fetchWatchlist,
  removeWatchlistItem,
  type WatchlistDetail,
  type WatchlistItemRead,
} from "@/lib/api";

export function WatchlistSection() {
  const [watchlists, setWatchlists] = useState<WatchlistDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [removingItems, setRemovingItems] = useState<Set<string>>(new Set());

  // Load watchlists on mount
  useEffect(() => {
    const loadWatchlists = async () => {
      try {
        setLoading(true);
        setError(null);
        const watchlistList = await fetchWatchlists();
        
        // Load details for each watchlist (including items and live quotes)
        const details = await Promise.all(
          watchlistList.map((w) => fetchWatchlist(w.id)),
        );
        setWatchlists(details);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load watchlists");
      } finally {
        setLoading(false);
      }
    };

    loadWatchlists();
  }, []);

  const handleRemoveItem = async (watchlistId: number, symbol: string) => {
    const itemKey = `${watchlistId}-${symbol}`;
    try {
      setRemovingItems((prev) => new Set(prev).add(itemKey));
      await removeWatchlistItem(watchlistId, symbol);

      // Update local state
      setWatchlists((prev) =>
        prev.map((w) =>
          w.id === watchlistId
            ? {
                ...w,
                items: w.items.filter((item) => item.symbol !== symbol),
                item_count: w.item_count - 1,
              }
            : w,
        ),
      );
    } catch (err) {
      setError(
        err instanceof Error ? err.message : `Failed to remove ${symbol}`,
      );
    } finally {
      setRemovingItems((prev) => {
        const next = new Set(prev);
        next.delete(itemKey);
        return next;
      });
    }
  };

  const formatPrice = (price: number | string | null): string => {
    if (price === null) return "--";
    const num = typeof price === "string" ? parseFloat(price) : price;
    if (Number.isNaN(num)) return "--";
    return num.toFixed(2);
  };

  const formatChange = (change: number | string | null): string => {
    if (change === null) return "--";
    const num = typeof change === "string" ? parseFloat(change) : change;
    if (Number.isNaN(num)) return "--";
    const sign = num >= 0 ? "+" : "";
    return `${sign}${num.toFixed(2)}%`;
  };

  const getChangeColor = (change: number | string | null): string => {
    if (change === null) return "text-muted-foreground";
    const num = typeof change === "string" ? parseFloat(change) : change;
    if (Number.isNaN(num)) return "text-muted-foreground";
    if (num > 0) return "text-green-400";
    if (num < 0) return "text-red-400";
    return "text-muted-foreground";
  };

  const getStatusBadge = (item: WatchlistItemRead): React.ReactNode => {
    if (!item.price) {
      return (
        <span className="inline-flex rounded-full border border-amber-300/20 bg-amber-300/10 px-2 py-1 text-[11px] text-amber-200">
          Awaiting data
        </span>
      );
    }
    return (
      <span className="inline-flex rounded-full border border-green-400/20 bg-green-400/10 px-2 py-1 text-[11px] text-green-300">
        Live
      </span>
    );
  };

  if (loading) {
    return (
      <section aria-labelledby="watchlist-title">
        <Card className="border-border/70 bg-card/80 shadow-none">
          <CardHeader className="flex-row items-start justify-between border-b border-border/60 px-5 py-5 sm:px-6">
            <div>
              <CardTitle id="watchlist-title" className="text-lg">
                Watchlist
              </CardTitle>
            </div>
            <Star className="mt-1 size-4 text-cyan-300" />
          </CardHeader>
          <CardContent className="flex items-center justify-center py-12">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              Loading watchlists...
            </div>
          </CardContent>
        </Card>
      </section>
    );
  }

  if (error) {
    return (
      <section aria-labelledby="watchlist-title">
        <Card className="border-border/70 bg-card/80 shadow-none">
          <CardHeader className="flex-row items-start justify-between border-b border-border/60 px-5 py-5 sm:px-6">
            <div>
              <CardTitle id="watchlist-title" className="text-lg">
                Watchlist
              </CardTitle>
            </div>
            <Star className="mt-1 size-4 text-cyan-300" />
          </CardHeader>
          <CardContent className="flex items-center gap-2 py-12 text-sm text-red-400">
            <AlertCircle className="size-4 flex-shrink-0" />
            <span>{error}</span>
          </CardContent>
        </Card>
      </section>
    );
  }

  const allItems = watchlists.flatMap((w) => w.items);

  return (
    <section aria-labelledby="watchlist-title">
      <Card className="border-border/70 bg-card/80 shadow-none">
        <CardHeader className="flex-row items-start justify-between border-b border-border/60 px-5 py-5 sm:px-6">
          <div>
            <CardTitle id="watchlist-title" className="text-lg">
              Watchlist
            </CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">
              {allItems.length} stock{allItems.length !== 1 ? "s" : ""} tracked
            </p>
          </div>
          <Star className="mt-1 size-4 text-cyan-300" />
        </CardHeader>
        <CardContent className="p-0">
          {allItems.length === 0 ? (
            <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
              No stocks in your watchlists yet. Add stocks from Stock Explorer.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[700px] text-left text-sm">
                <thead className="border-b border-border/60 text-xs text-muted-foreground">
                  <tr>
                    {[
                      "Company",
                      "Ticker",
                      "Exchange",
                      "Latest Price",
                      "Daily Change",
                      "Status",
                      "",
                    ].map((heading) => (
                      <th
                        key={heading}
                        className="px-5 py-3 font-medium sm:px-6"
                      >
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {allItems.map((item) => (
                    <tr
                      key={`${item.watchlist_id}-${item.symbol}`}
                      className="transition-colors hover:bg-muted/30"
                    >
                      <td className="px-5 py-4 font-medium text-foreground sm:px-6">
                        {item.name || item.symbol}
                      </td>
                      <td className="px-5 py-4 font-mono text-xs text-cyan-300 sm:px-6">
                        {item.symbol}
                      </td>
                      <td className="px-5 py-4 text-muted-foreground sm:px-6">
                        {item.exchange || "--"}
                      </td>
                      <td className="px-5 py-4 text-muted-foreground sm:px-6">
                        {formatPrice(item.price)}
                      </td>
                      <td
                        className={`px-5 py-4 sm:px-6 ${getChangeColor(item.percentage_change)}`}
                      >
                        {formatChange(item.percentage_change)}
                      </td>
                      <td className="px-5 py-4 sm:px-6">
                        {getStatusBadge(item)}
                      </td>
                      <td className="px-5 py-4 sm:px-6">
                        <button
                          onClick={() =>
                            handleRemoveItem(item.watchlist_id, item.symbol)
                          }
                          disabled={removingItems.has(
                            `${item.watchlist_id}-${item.symbol}`,
                          )}
                          className="inline-flex items-center justify-center transition-colors disabled:opacity-50"
                          aria-label={`Remove ${item.symbol}`}
                        >
                          {removingItems.has(
                            `${item.watchlist_id}-${item.symbol}`,
                          ) ? (
                            <Loader2 className="size-4 animate-spin text-muted-foreground" />
                          ) : (
                            <MoreHorizontal className="size-4 text-muted-foreground hover:text-foreground" />
                          )}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
