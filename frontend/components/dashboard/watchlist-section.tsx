import { MoreHorizontal, Star } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const companies = [
  { name: "Reliance Industries", ticker: "RELIANCE", exchange: "NSE" },
  { name: "Tata Consultancy Services", ticker: "TCS", exchange: "NSE" },
  { name: "HDFC Bank", ticker: "HDFCBANK", exchange: "NSE" },
];

export function WatchlistSection() {
  return (
    <section aria-labelledby="watchlist-title">
      <Card className="border-border/70 bg-card/80 shadow-none">
        <CardHeader className="flex-row items-start justify-between border-b border-border/60 px-5 py-5 sm:px-6">
          <div>
            <CardTitle id="watchlist-title" className="text-lg">Watchlist</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">Illustrative watchlist examples</p>
          </div>
          <Star className="mt-1 size-4 text-cyan-300" />
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[700px] text-left text-sm">
              <thead className="border-b border-border/60 text-xs text-muted-foreground">
                <tr>
                  {["Company", "Ticker", "Exchange", "Latest Price", "Daily Change", "Status", ""].map((heading) => <th key={heading} className="px-5 py-3 font-medium sm:px-6">{heading}</th>)}
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {companies.map((company) => (
                  <tr key={company.ticker} className="transition-colors hover:bg-muted/30">
                    <td className="px-5 py-4 font-medium text-foreground sm:px-6">{company.name}</td>
                    <td className="px-5 py-4 font-mono text-xs text-cyan-300 sm:px-6">{company.ticker}</td>
                    <td className="px-5 py-4 text-muted-foreground sm:px-6">{company.exchange}</td>
                    <td className="px-5 py-4 text-muted-foreground sm:px-6">--</td>
                    <td className="px-5 py-4 text-muted-foreground sm:px-6">--</td>
                    <td className="px-5 py-4 sm:px-6"><span className="inline-flex rounded-full border border-amber-300/20 bg-amber-300/10 px-2 py-1 text-[11px] text-amber-200">Awaiting data</span></td>
                    <td className="px-5 py-4 sm:px-6"><MoreHorizontal className="size-4 text-muted-foreground" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
