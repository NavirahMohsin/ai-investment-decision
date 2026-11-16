'use client';

import React, { useState, useEffect, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  FileText,
  Building2,
  TrendingUp,
  Search,
  Sparkles,
  Shield,
  Clock,
  Download,
  Bookmark,
  Trash2,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Layers,
  ArrowRight,
  ChevronRight,
  History,
  Activity,
  Zap,
} from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { fetchCompanies, Company } from '@/lib/api';
import apiClient from '@/lib/api-client';

const POPULAR_TICKERS = ['INFY', 'TCS', 'RELIANCE', 'HDFCBANK', 'ICICIBANK', 'WIPRO'];

interface SavedReport {
  id: string;
  ticker: string;
  companyName: string;
  reportType: string;
  timestamp: string;
  overview?: string;
  financialAnalysis?: string;
  swot?: string;
  report?: string;
}

export default function ResearchPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [ticker, setTicker] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'financials' | 'swot' | 'report' | 'history'>('overview');

  // Generation state
  const [reportType, setReportType] = useState<'comprehensive' | 'financial' | 'quick'>('comprehensive');
  const [language, setLanguage] = useState<'simple' | 'detailed'>('detailed');

  // Loading states
  const [loadingOverview, setLoadingOverview] = useState(false);
  const [loadingFinancials, setLoadingFinancials] = useState(false);
  const [loadingSwot, setLoadingSwot] = useState(false);
  const [loadingReport, setLoadingReport] = useState(false);
  const [loadingAll, setLoadingAll] = useState(false);

  // Content states
  const [overviewData, setOverviewData] = useState<string | null>(null);
  const [financialsData, setFinancialsData] = useState<string | null>(null);
  const [swotData, setSwotData] = useState<string | null>(null);
  const [reportData, setReportData] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Saved reports history (persisted in localStorage)
  const [savedReports, setSavedReports] = useState<SavedReport[]>([]);

  // Load companies & local history on mount
  useEffect(() => {
    fetchCompanies()
      .then(setCompanies)
      .catch((err) => console.warn('Could not load companies:', err));

    try {
      const stored = localStorage.getItem('arthai_saved_research');
      if (stored) {
        setSavedReports(JSON.parse(stored));
      }
    } catch (e) {
      console.warn('Could not load saved research history:', e);
    }
  }, []);

  // Filter companies for autocomplete
  const filteredCompanies = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const q = searchQuery.toUpperCase().trim();
    return companies
      .filter((c) => c.symbol.toUpperCase().includes(q) || c.name.toUpperCase().includes(q))
      .slice(0, 8);
  }, [companies, searchQuery]);

  const selectedCompany = useMemo(() => {
    return companies.find((c) => c.symbol.toUpperCase() === ticker.toUpperCase());
  }, [companies, ticker]);

  // Save current research to history
  const saveCurrentResearch = (
    sym: string,
    over?: string | null,
    fin?: string | null,
    sw?: string | null,
    rep?: string | null
  ) => {
    if (!sym) return;
    const compName = selectedCompany?.name || sym;
    const newEntry: SavedReport = {
      id: `${sym}-${Date.now()}`,
      ticker: sym,
      companyName: compName,
      reportType,
      timestamp: new Date().toISOString(),
      overview: over || overviewData || undefined,
      financialAnalysis: fin || financialsData || undefined,
      swot: sw || swotData || undefined,
      report: rep || reportData || undefined,
    };

    setSavedReports((prev) => {
      const updated = [newEntry, ...prev.filter((r) => r.ticker !== sym)].slice(0, 20);
      try {
        localStorage.setItem('arthai_saved_research', JSON.stringify(updated));
      } catch (e) {
        console.warn('Failed to save to localStorage:', e);
      }
      return updated;
    });
  };

  const deleteSavedReport = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSavedReports((prev) => {
      const updated = prev.filter((r) => r.id !== id);
      try {
        localStorage.setItem('arthai_saved_research', JSON.stringify(updated));
      } catch (err) {
        console.warn('Failed to delete from localStorage:', err);
      }
      return updated;
    });
  };

  const loadSavedReport = (item: SavedReport) => {
    setTicker(item.ticker);
    setOverviewData(item.overview || null);
    setFinancialsData(item.financialAnalysis || null);
    setSwotData(item.swot || null);
    setReportData(item.report || null);
    setActiveTab(item.report ? 'report' : item.overview ? 'overview' : 'financials');
  };

  // Generation Handlers
  const handleGenerateOverview = async () => {
    const sym = ticker.trim().toUpperCase();
    if (!sym) return;
    setErrorMsg(null);
    setLoadingOverview(true);
    try {
      const res = await apiClient.generateCompanyOverview(sym, language);
      if (res.status === 'success' && res.data) {
        const text = (res.data as any).overview || JSON.stringify(res.data);
        setOverviewData(text);
        saveCurrentResearch(sym, text, null, null, null);
      } else {
        setErrorMsg(res.error || 'Failed to generate company overview.');
      }
    } catch (err: any) {
      setErrorMsg(err?.message || 'Error connecting to research service.');
    } finally {
      setLoadingOverview(false);
    }
  };

  const handleGenerateFinancials = async () => {
    const sym = ticker.trim().toUpperCase();
    if (!sym) return;
    setErrorMsg(null);
    setLoadingFinancials(true);
    try {
      const res = await apiClient.analyzeFinancialPerformance(sym, '5Y');
      if (res.status === 'success' && res.data) {
        const text = (res.data as any).analysis || JSON.stringify(res.data);
        setFinancialsData(text);
        saveCurrentResearch(sym, null, text, null, null);
      } else {
        setErrorMsg(res.error || 'Failed to analyze financial performance.');
      }
    } catch (err: any) {
      setErrorMsg(err?.message || 'Error connecting to financial analysis service.');
    } finally {
      setLoadingFinancials(false);
    }
  };

  const handleGenerateSwot = async () => {
    const sym = ticker.trim().toUpperCase();
    if (!sym) return;
    setErrorMsg(null);
    setLoadingSwot(true);
    try {
      const res = await apiClient.generateSwotAnalysis(sym);
      if (res.status === 'success' && res.data) {
        const text = (res.data as any).swot || JSON.stringify(res.data);
        setSwotData(text);
        saveCurrentResearch(sym, null, null, text, null);
      } else {
        setErrorMsg(res.error || 'Failed to generate SWOT analysis.');
      }
    } catch (err: any) {
      setErrorMsg(err?.message || 'Error connecting to SWOT analysis service.');
    } finally {
      setLoadingSwot(false);
    }
  };

  const handleGenerateReport = async () => {
    const sym = ticker.trim().toUpperCase();
    if (!sym) return;
    setErrorMsg(null);
    setLoadingReport(true);
    try {
      const res = await apiClient.generateResearchReport(sym, reportType);
      if (res.status === 'success' && res.data) {
        const text = (res.data as any).report || JSON.stringify(res.data);
        setReportData(text);
        saveCurrentResearch(sym, null, null, null, text);
      } else {
        setErrorMsg(res.error || 'Failed to generate comprehensive research report.');
      }
    } catch (err: any) {
      setErrorMsg(err?.message || 'Error connecting to report service.');
    } finally {
      setLoadingReport(false);
    }
  };

  // Generate All in one click
  const handleGenerateFullDossier = async () => {
    const sym = ticker.trim().toUpperCase();
    if (!sym) return;
    setErrorMsg(null);
    setLoadingAll(true);
    try {
      await Promise.allSettled([
        handleGenerateOverview(),
        handleGenerateFinancials(),
        handleGenerateSwot(),
        handleGenerateReport(),
      ]);
      setActiveTab('report');
    } finally {
      setLoadingAll(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground pb-16">
      {/* Top Banner */}
      <div className="border-b border-border/60 bg-card/40 backdrop-blur px-6 py-3">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4 text-xs">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5 font-semibold text-primary">
              <Building2 className="size-4" />
              Company Research & Fundamental Intelligence
            </span>
            <Separator orientation="vertical" className="h-4" />
            <span className="text-muted-foreground">Comprehensive Equity Dossiers</span>
          </div>

          <div className="flex items-center gap-4 text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <History className="size-3 text-cyan-400" />
              Saved Reports: <strong className="text-foreground">{savedReports.length}</strong>
            </span>
            <Separator orientation="vertical" className="h-4" />
            <span className="flex items-center gap-1.5">
              <Zap className="size-3 text-emerald-400" />
              Real Fundamentals Data
            </span>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 pt-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2.5">
              Company Research Hub
              <Badge variant="outline" className="text-primary border-primary/40 font-mono text-[10px]">
                EQUITY ANALYSIS
              </Badge>
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Generate AI-powered executive overviews, 5-year financial performance reviews, strategic SWOT matrices,
              and institutional research reports.
            </p>
          </div>

          {savedReports.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setActiveTab('history')}
              className="self-start md:self-auto gap-1.5 text-xs border-border/80"
            >
              <Bookmark className="size-3.5 text-primary" />
              View Saved Research ({savedReports.length})
            </Button>
          )}
        </div>

        {/* Error Alert Banner */}
        {errorMsg && (
          <div className="mb-6 rounded-lg bg-rose-500/10 border border-rose-500/30 p-4 flex items-start gap-3 text-rose-300 text-sm">
            <AlertTriangle className="size-5 shrink-0 text-rose-400 mt-0.5" />
            <div className="flex-1">
              <strong className="font-semibold block mb-0.5">Research Service Notice</strong>
              {errorMsg}
            </div>
            <button onClick={() => setErrorMsg(null)} className="text-xs text-rose-400/80 hover:text-rose-300 underline">
              Dismiss
            </button>
          </div>
        )}

        {/* Search & Control Card */}
        <Card className="border-border/80 bg-card/60 backdrop-blur shadow-sm mb-6">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Search className="size-4 text-primary" />
                Select Target Stock
              </span>
              {selectedCompany && (
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-xs bg-primary/10 border-primary/30 text-primary">
                    {selectedCompany.name}
                  </Badge>
                  {selectedCompany.sector && (
                    <Badge variant="outline" className="text-[11px] text-muted-foreground">
                      {selectedCompany.sector}
                    </Badge>
                  )}
                </div>
              )}
            </CardTitle>
            <CardDescription className="text-xs">
              Search by company ticker or name from the Indian equity universe (NSE/BSE).
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4 pt-1">
            <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
              {/* Autocomplete Input */}
              <div className="md:col-span-6 relative">
                <Input
                  type="text"
                  placeholder="e.g. INFY, TCS, RELIANCE..."
                  value={ticker}
                  onChange={(e) => {
                    const val = e.target.value.toUpperCase();
                    setTicker(val);
                    setSearchQuery(val);
                    setShowDropdown(true);
                  }}
                  onFocus={() => setShowDropdown(true)}
                  className="font-mono text-sm uppercase tracking-wide pr-8"
                />
                {ticker && (
                  <button
                    onClick={() => {
                      setTicker('');
                      setSearchQuery('');
                    }}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground text-xs"
                  >
                    ×
                  </button>
                )}

                {/* Dropdown suggestions */}
                {showDropdown && filteredCompanies.length > 0 && (
                  <div className="absolute z-20 top-full left-0 right-0 mt-1 rounded-md border border-border bg-popover shadow-lg max-h-56 overflow-y-auto p-1 text-xs">
                    {filteredCompanies.map((c) => (
                      <div
                        key={c.symbol}
                        onClick={() => {
                          setTicker(c.symbol);
                          setShowDropdown(false);
                        }}
                        className="flex items-center justify-between px-3 py-2 rounded hover:bg-muted cursor-pointer transition-colors"
                      >
                        <div>
                          <span className="font-mono font-semibold text-primary">{c.symbol}</span>
                          <span className="text-muted-foreground ml-2 text-[11px] truncate">{c.name}</span>
                        </div>
                        <Badge variant="outline" className="text-[10px] scale-90">
                          {c.sector || c.exchange}
                        </Badge>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Format / Type selectors */}
              <div className="md:col-span-3 flex items-center gap-2">
                <select
                  value={reportType}
                  onChange={(e) => setReportType(e.target.value as any)}
                  className="w-full text-xs rounded-md bg-background border border-border p-2 text-foreground focus-visible:outline-none"
                >
                  <option value="comprehensive">Comprehensive Report</option>
                  <option value="financial">Financial Focus</option>
                  <option value="quick">Quick Overview</option>
                </select>
              </div>

              {/* Full dossier button */}
              <div className="md:col-span-3">
                <Button
                  onClick={handleGenerateFullDossier}
                  disabled={!ticker.trim() || loadingAll}
                  className="w-full font-medium text-xs gap-2 py-2"
                >
                  {loadingAll ? (
                    <>
                      <RefreshCw className="size-3.5 animate-spin" />
                      Generating Dossier...
                    </>
                  ) : (
                    <>
                      <Sparkles className="size-3.5" />
                      Generate Full Dossier
                    </>
                  )}
                </Button>
              </div>
            </div>

            {/* Quick Chips & Individual Actions */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-1 border-t border-border/40">
              <div className="flex flex-wrap items-center gap-1.5 text-xs">
                <span className="text-[11px] text-muted-foreground mr-1">Popular:</span>
                {POPULAR_TICKERS.map((sym) => (
                  <button
                    key={sym}
                    type="button"
                    onClick={() => {
                      setTicker(sym);
                      setShowDropdown(false);
                    }}
                    className={`text-[10px] font-mono px-2 py-0.5 rounded border transition-colors ${
                      ticker === sym
                        ? 'bg-primary/20 text-primary border-primary/50 font-semibold'
                        : 'bg-muted/40 text-muted-foreground hover:text-foreground border-border/60'
                    }`}
                  >
                    {sym}
                  </button>
                ))}
              </div>

              {/* Individual quick generation buttons */}
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="xs"
                  onClick={handleGenerateOverview}
                  disabled={!ticker.trim() || loadingOverview}
                  className="text-[11px] gap-1"
                >
                  {loadingOverview && <RefreshCw className="size-3 animate-spin" />}
                  Overview
                </Button>

                <Button
                  variant="outline"
                  size="xs"
                  onClick={handleGenerateFinancials}
                  disabled={!ticker.trim() || loadingFinancials}
                  className="text-[11px] gap-1"
                >
                  {loadingFinancials && <RefreshCw className="size-3 animate-spin" />}
                  Financials
                </Button>

                <Button
                  variant="outline"
                  size="xs"
                  onClick={handleGenerateSwot}
                  disabled={!ticker.trim() || loadingSwot}
                  className="text-[11px] gap-1"
                >
                  {loadingSwot && <RefreshCw className="size-3 animate-spin" />}
                  SWOT
                </Button>

                <Button
                  variant="outline"
                  size="xs"
                  onClick={handleGenerateReport}
                  disabled={!ticker.trim() || loadingReport}
                  className="text-[11px] gap-1"
                >
                  {loadingReport && <RefreshCw className="size-3 animate-spin" />}
                  Report
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Results Tabs & Container */}
        <Card className="border-border/80 bg-card/60 backdrop-blur shadow-sm overflow-hidden">
          {/* Tabs Bar */}
          <div className="border-b border-border/80 flex flex-wrap items-center justify-between px-4 bg-muted/20">
            <div className="flex gap-1 text-xs">
              <button
                onClick={() => setActiveTab('overview')}
                className={`px-4 py-3 font-semibold border-b-2 transition-all flex items-center gap-2 ${
                  activeTab === 'overview'
                    ? 'border-primary text-primary bg-background/60'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
              >
                <Building2 className="size-3.5" />
                Executive Overview
                {overviewData && <span className="size-1.5 rounded-full bg-emerald-400" />}
              </button>

              <button
                onClick={() => setActiveTab('financials')}
                className={`px-4 py-3 font-semibold border-b-2 transition-all flex items-center gap-2 ${
                  activeTab === 'financials'
                    ? 'border-primary text-primary bg-background/60'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
              >
                <TrendingUp className="size-3.5" />
                Financial Performance (5Y)
                {financialsData && <span className="size-1.5 rounded-full bg-emerald-400" />}
              </button>

              <button
                onClick={() => setActiveTab('swot')}
                className={`px-4 py-3 font-semibold border-b-2 transition-all flex items-center gap-2 ${
                  activeTab === 'swot'
                    ? 'border-primary text-primary bg-background/60'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
              >
                <Shield className="size-3.5" />
                Strategic SWOT Matrix
                {swotData && <span className="size-1.5 rounded-full bg-emerald-400" />}
              </button>

              <button
                onClick={() => setActiveTab('report')}
                className={`px-4 py-3 font-semibold border-b-2 transition-all flex items-center gap-2 ${
                  activeTab === 'report'
                    ? 'border-primary text-primary bg-background/60'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
              >
                <FileText className="size-3.5" />
                Full Research Report
                {reportData && <span className="size-1.5 rounded-full bg-emerald-400" />}
              </button>

              <button
                onClick={() => setActiveTab('history')}
                className={`px-4 py-3 font-semibold border-b-2 transition-all flex items-center gap-2 ${
                  activeTab === 'history'
                    ? 'border-primary text-primary bg-background/60'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
              >
                <Bookmark className="size-3.5" />
                Saved History ({savedReports.length})
              </button>
            </div>
          </div>

          <CardContent className="p-6">
            {/* TAB 1: Company Overview */}
            {activeTab === 'overview' && (
              <div>
                {loadingOverview ? (
                  <div className="py-16 text-center space-y-3">
                    <RefreshCw className="size-6 animate-spin text-primary mx-auto" />
                    <p className="text-xs text-muted-foreground">Synthesising company business model and market position...</p>
                  </div>
                ) : overviewData ? (
                  <div className="prose prose-invert prose-slate max-w-none prose-headings:text-foreground prose-h1:text-xl prose-h2:text-lg prose-p:text-muted-foreground text-sm">
                    <ReactMarkdown>{overviewData}</ReactMarkdown>
                  </div>
                ) : (
                  <div className="text-center py-16 text-muted-foreground text-xs space-y-2">
                    <Building2 className="size-8 mx-auto text-muted-foreground/40 mb-2" />
                    <p className="text-foreground font-medium">No overview generated yet</p>
                    <p>Enter a stock ticker above and click "Overview" or "Generate Full Dossier".</p>
                  </div>
                )}
              </div>
            )}

            {/* TAB 2: Financial Performance */}
            {activeTab === 'financials' && (
              <div>
                {loadingFinancials ? (
                  <div className="py-16 text-center space-y-3">
                    <RefreshCw className="size-6 animate-spin text-primary mx-auto" />
                    <p className="text-xs text-muted-foreground">Evaluating 5-year financial ratios, margins and balance-sheet health...</p>
                  </div>
                ) : financialsData ? (
                  <div className="prose prose-invert prose-slate max-w-none prose-headings:text-foreground prose-h1:text-xl prose-h2:text-lg prose-p:text-muted-foreground text-sm">
                    <ReactMarkdown>{financialsData}</ReactMarkdown>
                  </div>
                ) : (
                  <div className="text-center py-16 text-muted-foreground text-xs space-y-2">
                    <TrendingUp className="size-8 mx-auto text-muted-foreground/40 mb-2" />
                    <p className="text-foreground font-medium">No financial performance analysis generated yet</p>
                    <p>Click "Financials" above to evaluate verified financial statements.</p>
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: SWOT Matrix */}
            {activeTab === 'swot' && (
              <div>
                {loadingSwot ? (
                  <div className="py-16 text-center space-y-3">
                    <RefreshCw className="size-6 animate-spin text-primary mx-auto" />
                    <p className="text-xs text-muted-foreground">Extracting internal strengths/weaknesses and market opportunities/threats...</p>
                  </div>
                ) : swotData ? (
                  <div className="prose prose-invert prose-slate max-w-none prose-headings:text-foreground prose-h1:text-xl prose-h2:text-lg prose-p:text-muted-foreground text-sm">
                    <ReactMarkdown>{swotData}</ReactMarkdown>
                  </div>
                ) : (
                  <div className="text-center py-16 text-muted-foreground text-xs space-y-2">
                    <Shield className="size-8 mx-auto text-muted-foreground/40 mb-2" />
                    <p className="text-foreground font-medium">No SWOT analysis generated yet</p>
                    <p>Click "SWOT" to evaluate strategic competitive positioning.</p>
                  </div>
                )}
              </div>
            )}

            {/* TAB 4: Full Report */}
            {activeTab === 'report' && (
              <div>
                {loadingReport ? (
                  <div className="py-16 text-center space-y-3">
                    <RefreshCw className="size-6 animate-spin text-primary mx-auto" />
                    <p className="text-xs text-muted-foreground">Composing comprehensive equity research report...</p>
                  </div>
                ) : reportData ? (
                  <div className="space-y-4">
                    <div className="prose prose-invert prose-slate max-w-none prose-headings:text-foreground prose-h1:text-xl prose-h2:text-lg prose-p:text-muted-foreground text-sm">
                      <ReactMarkdown>{reportData}</ReactMarkdown>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-16 text-muted-foreground text-xs space-y-2">
                    <FileText className="size-8 mx-auto text-muted-foreground/40 mb-2" />
                    <p className="text-foreground font-medium">No research report generated yet</p>
                    <p>Select a stock ticker and click "Generate Full Dossier" or "Report".</p>
                  </div>
                )}
              </div>
            )}

            {/* TAB 5: Saved History */}
            {activeTab === 'history' && (
              <div className="space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-border/40 text-xs">
                  <span className="font-semibold text-foreground">Previously Saved Dossiers</span>
                  <span className="text-muted-foreground">{savedReports.length} stored locally</span>
                </div>

                {savedReports.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
                    {savedReports.map((item) => (
                      <div
                        key={item.id}
                        onClick={() => loadSavedReport(item)}
                        className="p-3.5 rounded-lg border border-border/80 bg-card hover:bg-muted/30 transition-all cursor-pointer flex items-center justify-between gap-3 text-xs"
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-bold text-primary text-sm">{item.ticker}</span>
                            <span className="text-muted-foreground truncate font-medium">{item.companyName}</span>
                          </div>
                          <div className="flex items-center gap-2 text-[10px] text-muted-foreground mt-1">
                            <span>
                              {new Date(item.timestamp).toLocaleDateString('en-IN', {
                                day: '2-digit',
                                month: 'short',
                                year: 'numeric',
                              })}
                            </span>
                            <span>•</span>
                            <span className="capitalize">{item.reportType}</span>
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          <Button variant="ghost" size="xs" className="h-7 text-xs">
                            Load <ChevronRight className="size-3 ml-1" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon-xs"
                            onClick={(e) => deleteSavedReport(item.id, e)}
                            className="text-muted-foreground hover:text-rose-400"
                          >
                            <Trash2 className="size-3.5" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12 text-muted-foreground text-xs">
                    No research reports saved yet. When you generate reports, they will be saved here automatically.
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Disclaimer Card */}
        <div className="mt-6 p-4 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs flex items-start gap-3">
          <Shield className="size-4 shrink-0 text-amber-400 mt-0.5" />
          <div className="leading-relaxed">
            <strong>Financial Disclaimer:</strong> All intelligence, financial analyses, and SWOT assessments are
            generated from verified historical statements and market data. They do not constitute investment advice or a
            solicitation to buy or sell securities. Always verify with official regulatory filings and a licensed
            financial advisor.
          </div>
        </div>
      </div>
    </div>
  );
}
