"use client";

import { useState } from "react";
import Link from "next/link";
import { Bell, Menu, Search, LogOut, Settings as SettingsIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Sidebar } from "@/components/layout/sidebar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";

export function Topbar({ title }: { title: string }) {
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [notificationsOpen, setNotificationsOpen] = useState(false);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      // Navigate to search results
      window.location.href = `/stocks?search=${encodeURIComponent(searchQuery)}`;
      setSearchOpen(false);
    }
  };

  return (
    <>
      <header className="flex h-18 items-center justify-between border-b border-border/70 bg-background/90 px-4 backdrop-blur-md sm:px-8">
        <div className="flex items-center gap-3">
          <Sheet>
            <SheetTrigger render={<Button variant="ghost" size="icon" className="md:hidden" aria-label="Open navigation" />}>
              <Menu className="size-5" />
            </SheetTrigger>
            <SheetContent side="left" className="w-72 border-sidebar-border bg-sidebar p-0 text-sidebar-foreground" showCloseButton={false}>
              <SheetTitle className="sr-only">ArthAI navigation</SheetTitle>
              <Sidebar mobile />
            </SheetContent>
          </Sheet>
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">Workspace</p>
            <h1 className="text-base font-semibold text-foreground sm:text-lg">{title}</h1>
          </div>
        </div>

        <div className="flex items-center gap-1 sm:gap-3">
          {/* Search Button */}
          <Button
            variant="ghost"
            size="icon"
            aria-label="Search stocks"
            onClick={() => setSearchOpen(true)}
          >
            <Search className="size-4" />
          </Button>

          {/* Notifications Button */}
          <DropdownMenu open={notificationsOpen} onOpenChange={setNotificationsOpen}>
            <DropdownMenuTrigger>
              <Button variant="ghost" size="icon" aria-label="Notifications">
                <Bell className="size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-80">
              <div className="px-4 py-2">
                <h3 className="font-semibold text-sm">Notifications</h3>
                <p className="text-xs text-muted-foreground mt-1">
                  Notification system coming soon. Enable notifications in settings.
                </p>
              </div>
              <DropdownMenuSeparator />
              <DropdownMenuItem>
                <Link href="/settings" className="flex w-full cursor-pointer items-center">
                  <SettingsIcon className="mr-2 size-4" />
                  Notification Settings
                </Link>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* User Avatar / Profile Menu */}
          <DropdownMenu>
            <DropdownMenuTrigger>
              <button className="ml-1 flex size-8 items-center justify-center rounded-full border border-cyan-400/30 bg-cyan-400/10 text-xs font-semibold text-cyan-300 hover:border-cyan-400/50 hover:bg-cyan-400/20 transition-colors cursor-pointer" aria-label="User menu">
                AI
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem disabled className="text-xs">
                <span className="text-muted-foreground">Signed in as</span>
              </DropdownMenuItem>
              <DropdownMenuItem disabled className="font-semibold">
                AI Assistant
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem>
                <Link href="/settings" className="flex w-full cursor-pointer items-center">
                  <SettingsIcon className="mr-2 size-4" />
                  Settings
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="text-destructive cursor-pointer">
                <LogOut className="mr-2 size-4" />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      {/* Search Dialog */}
      {searchOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80">
          <div className="w-full max-w-md rounded-lg border border-border/70 bg-card/95 p-6 shadow-lg">
            <h2 className="text-lg font-semibold mb-2">Search Stocks</h2>
            <p className="text-sm text-muted-foreground mb-4">
              Enter a stock symbol or company name to find detailed information
            </p>
            <form onSubmit={handleSearch} className="space-y-4">
              <div className="flex gap-2">
                <Input
                  placeholder="e.g., RELIANCE, TCS, HDFCBANK"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  autoFocus
                  className="flex-1"
                />
                <Button type="submit" disabled={!searchQuery.trim()}>
                  Search
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Supported: Indian market stocks (NSE)
              </p>
            </form>
            <button
              onClick={() => setSearchOpen(false)}
              className="absolute right-4 top-4 text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Close search"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </>
  );
}
