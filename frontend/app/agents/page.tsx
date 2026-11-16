'use client';

import React, { useState, useEffect, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  Brain,
  TrendingUp,
  Building2,
  Newspaper,
  Cpu,
  ShieldAlert,
  Search,
  Sparkles,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  SlidersHorizontal,
  FileText,
  Activity,
  Layers,
  ArrowRight,
  Info,
  Database,
  ExternalLink,
  RotateCcw,
  Check,
  Zap,
} from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { fetchCompanies, Company } from '@/lib/api';
import {
  apiClient,
  AgentMetadata,
  AgentsHealthData,
  AgentExecutionResponse,
  AgentResultDetail,
} from '@/lib/api-client';

// ---------------------------------------------------------------------------
// Constants & Agent Definitions
// ---------------------------------------------------------------------------

const AGENT_ICON_MAP: Record<string, React.ReactNode> = {
  market_analyst: <TrendingUp className="size-4 text-cyan-400" />,
  fundamental_analyst: <Building2 className="size-4 text-emerald-400" />,
  news_analyst: <Newspaper className="size-4 text-amber-400" />,
  ml_analyst: <Cpu className="size-4 text-purple-400" />,
  risk_analyst: <ShieldAlert className="size-4 text-rose-400" />,
  coordinator: <Brain className="size-4 text-blue-400" />,
};

const DEFAULT_AGENTS = [
  {
    name: 'market_analyst',
    display_name: 'Market Analyst',
    description: 'Technical indicators (SMA, EMA, RSI, MACD, Bollinger Bands, ATR), price action & momentum.',
  },
  {
    name: 'fundamental_analyst',
    display_name: 'Fundamental Analyst',
    description: 'Financial ratios, balance sheet health, profitability, valuation multiples & scoring.',
  },
  {
    name: 'news_analyst',
    display_name: 'News Analyst',
    description: 'Recent coverage, event categorisation, sentiment scoring & headline impact.',
  },
  {
    name: 'ml_analyst',
    display_name: 'ML Analyst',
    description: 'Predictive machine learning models, directional probabilities & evaluation metrics.',
  },
  {
    name: 'risk_analyst',
    display_name: 'Risk Analyst',
    description: 'Deterministic volatility, max drawdown, worst daily decline & cross-agent signal consistency.',
  },
];

const POPULAR_TICKERS = ['INFY', 'TCS', 'RELIANCE', 'HDFCBANK', 'ICICIBANK', 'WIPRO'];

// Helper to format currency / numbers in Indian notation
function formatINRValue(val: any): string {
  if (val === null || val === undefined) return 'N/A';
  if (typeof val === 'number') {
    if (Math.abs(val) >= 10000000) {
      return `₹${(val / 10000000).toFixed(2)} Cr`;
    }
    if (Math.abs(val) >= 100000) {
      return `₹${(val / 100000).toFixed(2)} L`;
    }
    return val.toLocaleString('en-IN', { maximumFractionDigits: 2 });
  }
  return String(val);
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function AgentsWorkspacePage() {
  // State: Companies & Search
  const [companies, setCompanies] = useState<Company[]>([]);
  const [tickerInput, setTickerInput] = useState('');
  const [tickerSearchQuery, setTickerSearchQuery] = useState('');
  const [showCompanyDropdown, setShowCompanyDropdown] = useState(false);

  // State: Form Options
  const [researchMode, setResearchMode] = useState<'ticker' | 'analyze'>('ticker');
  const [customQuestion, setCustomQuestion] = useState('');
  const [nlQuery, setNlQuery] = useState('');
  const [scope, setScope] = useState<'quick' | 'standard' | 'deep'>('standard');
  const [isSelectiveMode, setIsSelectiveMode] = useState(false);
  const [selectedAgentNames, setSelectedAgentNames] = useState<string[]>([
    'market_analyst',
    'fundamental_analyst',
    'news_analyst',
    'risk_analyst',
  ]);

  // State: System Health & Metadata
  const [health, setHealth] = useState<AgentsHealthData | null>(null);
  const [agentsList, setAgentsList] = useState<AgentMetadata[]>([]);

  // State: Execution & Report
  const [isRunning, setIsRunning] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [executionResult, setExecutionResult] = useState<AgentExecutionResponse | null>(null);

  // State: UI View Tabs
  const [activeTab, setActiveTab] = useState<'report' | 'specialists' | 'evidence'>('report');
  const [expandedSpecialist, setExpandedSpecialist] = useState<string | null>('market_analyst');

  // Load companies and agent metadata on mount
  useEffect(() => {
    async function init() {
      try {
        const compList = await fetchCompanies();
        setCompanies(compList);
      } catch (e) {
        console.warn('Could not load companies list:', e);
      }

      try {
        const hRes = await apiClient.checkAgentsHealth();
        if (hRes.status === 'success' && hRes.data) {
          setHealth(hRes.data);
        }
      } catch (e) {
        console.warn('Could not load health:', e);
      }

      try {
        const listRes = await apiClient.listAgents();
        if (listRes.status === 'success' && listRes.data) {
          setAgentsList(listRes.data.agents);
        }
      } catch (e) {
        console.warn('Could not list agents:', e);
      }
    }
    init();
  }, []);

  // Filter companies for autocomplete
  const filteredCompanies = useMemo(() => {
    if (!tickerSearchQuery.trim()) return [];
    const q = tickerSearchQuery.toUpperCase().trim();
    return companies
      .filter((c) => c.symbol.toUpperCase().includes(q) || c.name.toUpperCase().includes(q))
      .slice(0, 8);
  }, [companies, tickerSearchQuery]);

  // Handle agent selection toggling
  const toggleAgent = (name: string) => {
    setSelectedAgentNames((prev) =>
      prev.includes(name) ? prev.filter((a) => a !== name) : [...prev, name]
    );
  };

  const selectAllAgents = () => {
    setSelectedAgentNames([
      'market_analyst',
      'fundamental_analyst',
      'news_analyst',
      'ml_analyst',
      'risk_analyst',
    ]);
  };

  const clearSelectedAgents = () => {
    setSelectedAgentNames(['market_analyst']);
  };

  // Adjust default selection when scope changes in comprehensive mode
  useEffect(() => {
    if (!isSelectiveMode) {
      if (scope === 'quick') {
        setSelectedAgentNames(['market_analyst']);
      } else if (scope === 'standard') {
        setSelectedAgentNames([
          'market_analyst',
          'fundamental_analyst',
          'news_analyst',
          'risk_analyst',
        ]);
      } else {
        setSelectedAgentNames([
          'market_analyst',
          'fundamental_analyst',
          'news_analyst',
          'risk_analyst',
          'ml_analyst',
        ]);
      }
    }
  }, [scope, isSelectiveMode]);

  // Execute workflow
  const handleStartAnalysis = async () => {
    setErrorMsg(null);

    if (researchMode === 'ticker') {
      const sym = tickerInput.trim().toUpperCase();
      if (!sym) {
        setErrorMsg('Please select or enter a valid stock ticker symbol.');
        return;
      }

      setIsRunning(true);
      try {
        const response = await apiClient.runAgentResearch(
          sym,
          customQuestion.trim() || undefined,
          scope,
          isSelectiveMode ? selectedAgentNames : undefined
        );

        if (response.status === 'success' && response.data) {
          setExecutionResult(response.data);
          setActiveTab('report');
        } else {
          setErrorMsg(response.error || 'Failed to complete research workflow.');
        }
      } catch (err: any) {
        setErrorMsg(err?.message || 'Network error executing agent research.');
      } finally {
        setIsRunning(false);
      }
    } else {
      // Natural language analyze mode
      const query = nlQuery.trim();
      if (!query) {
        setErrorMsg('Please enter a natural language research request.');
        return;
      }

      setIsRunning(true);
      try {
        const response = await apiClient.runAgentAnalyze(
          query,
          tickerInput.trim() ? [tickerInput.trim().toUpperCase()] : undefined,
          scope,
          isSelectiveMode ? selectedAgentNames : undefined
        );

        if (response.status === 'success' && response.data) {
          setExecutionResult(response.data);
          setActiveTab('report');
        } else {
          setErrorMsg(response.error || 'Failed to complete natural language analysis.');
        }
      } catch (err: any) {
        setErrorMsg(err?.message || 'Network error executing agent analysis.');
      } finally {
        setIsRunning(false);
      }
    }
  };

  const handleReset = () => {
    setTickerInput('');
    setTickerSearchQuery('');
    setCustomQuestion('');
    setNlQuery('');
    setExecutionResult(null);
    setErrorMsg(null);
  };

  // Helper for badge colors based on status
  const getStatusBadge = (statusStr?: string) => {
    switch (statusStr) {
      case 'completed':
        return <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30">Completed</Badge>;
      case 'running':
        return <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30 animate-pulse">Running</Badge>;
      case 'failed':
        return <Badge className="bg-rose-500/20 text-rose-400 border-rose-500/30">Failed</Badge>;
      case 'skipped':
        return <Badge className="bg-slate-500/20 text-slate-400 border-slate-500/30">Skipped</Badge>;
      case 'pending':
        return <Badge className="bg-amber-500/20 text-amber-400 border-amber-500/30">Pending</Badge>;
      default:
        return <Badge variant="outline">Unknown</Badge>;
    }
  };

  const getConfidenceBadge = (confidence?: string) => {
    switch (confidence?.toLowerCase()) {
      case 'high':
        return <Badge className="bg-emerald-500/20 text-emerald-300 border-emerald-500/30">High Confidence</Badge>;
      case 'medium':
        return <Badge className="bg-cyan-500/20 text-cyan-300 border-cyan-500/30">Medium Confidence</Badge>;
      default:
        return <Badge className="bg-amber-500/20 text-amber-300 border-amber-500/30">Low Confidence</Badge>;
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground pb-16">
      {/* Top Banner / System Health Bar */}
      <div className="border-b border-border/60 bg-card/40 backdrop-blur px-6 py-3">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4 text-xs">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5 font-semibold text-primary">
              <Brain className="size-4" />
              ArthAI Multi-Agent Intelligence Workspace
            </span>
            <Separator orientation="vertical" className="h-4" />
            <span className="text-muted-foreground">Phase 5 LangGraph Orchestrator</span>
          </div>

          <div className="flex items-center gap-4 text-muted-foreground">
            {health && (
              <>
                <div className="flex items-center gap-1.5">
                  <span
                    className={`size-2 rounded-full ${
                      health.status === 'healthy'
                        ? 'bg-emerald-500'
                        : health.status === 'degraded'
                        ? 'bg-amber-500'
                        : 'bg-rose-500'
                    }`}
                  />
                  <span>
                    Status:{' '}
                    <strong className="capitalize text-foreground font-medium">{health.status}</strong>
                  </span>
                </div>

                <div className="hidden sm:flex items-center gap-1.5">
                  <Zap className="size-3 text-cyan-400" />
                  <span>
                    Active LLMs:{' '}
                    <strong className="text-foreground font-medium">
                      {health.active_providers.length > 0
                        ? health.active_providers.join(', ').toUpperCase()
                        : 'Rule-Based Fallback'}
                    </strong>
                  </span>
                </div>

                <div className="flex items-center gap-1.5">
                  <Layers className="size-3 text-purple-400" />
                  <span>
                    Specialists: <strong className="text-foreground font-medium">{health.total_agents}</strong>
                  </span>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 pt-6">
        {/* Workspace Title & Intro */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2.5">
              Financial Intelligence Workspace
              <Badge variant="outline" className="text-primary border-primary/40 font-mono text-[10px]">
                LANGGRAPH v1.2
              </Badge>
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Coordinate autonomous specialist agents to perform grounded, multi-dimensional analysis on Indian equities.
            </p>
          </div>

          {executionResult && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleReset}
              className="self-start md:self-auto gap-1.5 text-xs border-border/80"
            >
              <RotateCcw className="size-3.5" />
              Start New Analysis
            </Button>
          )}
        </div>

        {/* Error Alert Banner */}
        {errorMsg && (
          <div className="mb-6 rounded-lg bg-rose-500/10 border border-rose-500/30 p-4 flex items-start gap-3 text-rose-300 text-sm">
            <AlertTriangle className="size-5 shrink-0 text-rose-400 mt-0.5" />
            <div className="flex-1">
              <strong className="font-semibold block mb-0.5">Execution Error</strong>
              {errorMsg}
            </div>
            <button
              onClick={() => setErrorMsg(null)}
              className="text-xs text-rose-400/80 hover:text-rose-300 underline"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Partial Failure Warning Banner */}
        {executionResult && executionResult.status === 'partial_failure' && (
          <div className="mb-6 rounded-lg bg-amber-500/10 border border-amber-500/30 p-4 flex items-start gap-3 text-amber-300 text-sm">
            <Info className="size-5 shrink-0 text-amber-400 mt-0.5" />
            <div className="flex-1">
              <strong className="font-semibold block mb-0.5">Partial Success</strong>
              One or more specialist agents encountered data limitations or errors. Verified findings from
              completed specialist agents are consolidated below.
            </div>
          </div>
        )}

        {/* MAIN WORKSPACE GRID */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* LEFT COLUMN: Request Panel & Agent Selector (4 cols on lg) */}
          <div className="lg:col-span-5 space-y-6">
            {/* Panel 1: Research Request Configuration */}
            <Card className="border-border/80 bg-card/60 backdrop-blur shadow-sm">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <Search className="size-4 text-primary" />
                    1. Research Request
                  </span>
                  <div className="flex rounded-md p-0.5 bg-muted/60 text-[11px]">
                    <button
                      onClick={() => setResearchMode('ticker')}
                      className={`px-2.5 py-1 rounded transition-all font-medium ${
                        researchMode === 'ticker'
                          ? 'bg-primary text-primary-foreground shadow-xs'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      Ticker Target
                    </button>
                    <button
                      onClick={() => setResearchMode('analyze')}
                      className={`px-2.5 py-1 rounded transition-all font-medium ${
                        researchMode === 'analyze'
                          ? 'bg-primary text-primary-foreground shadow-xs'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      Natural Language
                    </button>
                  </div>
                </CardTitle>
                <CardDescription className="text-xs">
                  {researchMode === 'ticker'
                    ? 'Target a validated stock ticker from the Indian company universe.'
                    : 'Prompt the coordinator with free-text financial intelligence requests.'}
                </CardDescription>
              </CardHeader>

              <CardContent className="space-y-4 pt-1">
                {/* Ticker Search / Autocomplete */}
                <div className="space-y-1.5 relative">
                  <label className="text-xs font-medium text-foreground/80 flex items-center justify-between">
                    <span>Stock Symbol (NSE/BSE)</span>
                    <span className="text-[11px] text-muted-foreground">
                      {companies.length} tracked companies
                    </span>
                  </label>
                  <div className="relative">
                    <Input
                      type="text"
                      placeholder="e.g. INFY, TCS, RELIANCE..."
                      value={tickerInput}
                      onChange={(e) => {
                        const val = e.target.value.toUpperCase();
                        setTickerInput(val);
                        setTickerSearchQuery(val);
                        setShowCompanyDropdown(true);
                      }}
                      onFocus={() => setShowCompanyDropdown(true)}
                      className="font-mono text-sm uppercase tracking-wide pr-8"
                    />
                    {tickerInput && (
                      <button
                        onClick={() => {
                          setTickerInput('');
                          setTickerSearchQuery('');
                        }}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground text-xs"
                      >
                        ×
                      </button>
                    )}
                  </div>

                  {/* Autocomplete dropdown */}
                  {showCompanyDropdown && filteredCompanies.length > 0 && (
                    <div className="absolute z-20 top-full left-0 right-0 mt-1 rounded-md border border-border bg-popover shadow-lg max-h-56 overflow-y-auto p-1 text-xs">
                      {filteredCompanies.map((c) => (
                        <div
                          key={c.symbol}
                          onClick={() => {
                            setTickerInput(c.symbol);
                            setShowCompanyDropdown(false);
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

                  {/* Popular Pills */}
                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                    <span className="text-[11px] text-muted-foreground mr-1">Popular:</span>
                    {POPULAR_TICKERS.map((sym) => (
                      <button
                        key={sym}
                        type="button"
                        onClick={() => {
                          setTickerInput(sym);
                          setShowCompanyDropdown(false);
                        }}
                        className={`text-[10px] font-mono px-2 py-0.5 rounded border transition-colors ${
                          tickerInput === sym
                            ? 'bg-primary/20 text-primary border-primary/50 font-semibold'
                            : 'bg-muted/40 text-muted-foreground hover:text-foreground border-border/60'
                        }`}
                      >
                        {sym}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Question / NL Input */}
                {researchMode === 'ticker' ? (
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-foreground/80">
                      Specific Research Question <span className="text-muted-foreground">(Optional)</span>
                    </label>
                    <textarea
                      rows={2}
                      placeholder="e.g. Evaluate whether recent technical momentum is supported by balance sheet health."
                      value={customQuestion}
                      onChange={(e) => setCustomQuestion(e.target.value)}
                      className="w-full text-xs rounded-md bg-background border border-border/80 p-2.5 text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary resize-none"
                    />
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-foreground/80">
                      Natural Language Prompt <span className="text-primary">*</span>
                    </label>
                    <textarea
                      rows={3}
                      placeholder="e.g. Conduct a comprehensive investment analysis on Infosys and highlight any contradictions between technical trend and news coverage."
                      value={nlQuery}
                      onChange={(e) => setNlQuery(e.target.value)}
                      className="w-full text-xs rounded-md bg-background border border-border/80 p-2.5 text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary resize-none"
                    />
                  </div>
                )}

                {/* Scope Selection */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-foreground/80">Analysis Scope</label>
                    <span className="text-[10px] text-muted-foreground font-mono uppercase">
                      {scope === 'quick' ? '1 Specialist' : scope === 'standard' ? '4 Specialists' : 'All 5 Specialists'}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    {(
                      [
                        { id: 'quick', label: 'Quick', desc: 'Market only' },
                        { id: 'standard', label: 'Standard', desc: 'Core 4' },
                        { id: 'deep', label: 'Deep', desc: '5 + ML' },
                      ] as const
                    ).map((s) => (
                      <button
                        key={s.id}
                        type="button"
                        onClick={() => setScope(s.id)}
                        className={`p-2 rounded-md border text-left transition-all ${
                          scope === s.id
                            ? 'bg-primary/10 border-primary text-foreground shadow-xs font-medium'
                            : 'bg-muted/30 border-border/60 text-muted-foreground hover:bg-muted/50 hover:text-foreground'
                        }`}
                      >
                        <div className="font-semibold text-xs capitalize">{s.label}</div>
                        <div className="text-[10px] text-muted-foreground">{s.desc}</div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Selective Execution Toggle */}
                <div className="pt-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground flex items-center gap-1.5">
                      <SlidersHorizontal className="size-3.5 text-primary" />
                      Custom Specialist Override
                    </span>
                    <button
                      type="button"
                      onClick={() => setIsSelectiveMode(!isSelectiveMode)}
                      className={`text-xs font-medium px-2 py-0.5 rounded transition-colors ${
                        isSelectiveMode
                          ? 'bg-primary/20 text-primary border border-primary/40'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      {isSelectiveMode ? 'Active (Manual)' : 'Scope Default'}
                    </button>
                  </div>
                </div>

                {/* Submit Action Button */}
                <Button
                  onClick={handleStartAnalysis}
                  disabled={isRunning || (researchMode === 'ticker' ? !tickerInput.trim() : !nlQuery.trim())}
                  className="w-full mt-2 font-medium py-2.5 gap-2 shadow-sm"
                >
                  {isRunning ? (
                    <>
                      <RefreshCw className="size-4 animate-spin" />
                      Running LangGraph Workflow...
                    </>
                  ) : (
                    <>
                      <Sparkles className="size-4" />
                      Launch Specialist Workflow
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            {/* Panel 2: Agent Selection / Roster */}
            <Card className="border-border/80 bg-card/60 backdrop-blur shadow-sm">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Brain className="size-4 text-primary" />
                    2. Specialist Agents Roster
                  </CardTitle>
                  {isSelectiveMode && (
                    <div className="flex items-center gap-2 text-[10px]">
                      <button
                        onClick={selectAllAgents}
                        className="text-primary hover:underline font-medium"
                      >
                        All
                      </button>
                      <span className="text-muted-foreground">•</span>
                      <button
                        onClick={clearSelectedAgents}
                        className="text-muted-foreground hover:underline"
                      >
                        Clear
                      </button>
                    </div>
                  )}
                </div>
                <CardDescription className="text-xs">
                  {isSelectiveMode
                    ? 'Click to toggle specific agents for targeted analysis.'
                    : `Active agents derived automatically from ${scope.toUpperCase()} scope.`}
                </CardDescription>
              </CardHeader>

              <CardContent className="space-y-2.5 pt-0">
                {DEFAULT_AGENTS.map((agent) => {
                  const isSelected = selectedAgentNames.includes(agent.name);

                  return (
                    <div
                      key={agent.name}
                      onClick={() => {
                        if (isSelectiveMode) toggleAgent(agent.name);
                      }}
                      className={`p-2.5 rounded-lg border transition-all text-xs flex items-start gap-3 ${
                        isSelectiveMode ? 'cursor-pointer' : 'cursor-default'
                      } ${
                        isSelected
                          ? 'bg-card border-border shadow-xs'
                          : 'bg-muted/20 border-border/40 opacity-60'
                      }`}
                    >
                      <div className="p-1.5 rounded bg-muted/60 shrink-0 mt-0.5">
                        {AGENT_ICON_MAP[agent.name] || <Activity className="size-4 text-primary" />}
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-semibold text-foreground flex items-center gap-1.5">
                            {agent.display_name}
                            {agent.name === 'ml_analyst' && (
                              <span className="text-[9px] px-1 py-0.2 rounded bg-purple-500/10 text-purple-400 font-mono">
                                DEEP SCOPE
                              </span>
                            )}
                          </span>

                          <div className="flex items-center gap-1.5 shrink-0">
                            <span className="size-1.5 rounded-full bg-emerald-500" />
                            <span className="text-[10px] text-muted-foreground">Available</span>
                          </div>
                        </div>

                        <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">
                          {agent.description}
                        </p>
                      </div>

                      {isSelectiveMode && (
                        <div className="shrink-0 mt-1">
                          <div
                            className={`size-4 rounded flex items-center justify-center border transition-colors ${
                              isSelected
                                ? 'bg-primary border-primary text-primary-foreground'
                                : 'border-muted-foreground/40'
                            }`}
                          >
                            {isSelected && <Check className="size-3 stroke-[3]" />}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}

                {/* Coordinator Note */}
                <div className="p-2.5 rounded-lg border border-border/40 bg-muted/10 text-xs flex items-center gap-2.5 text-muted-foreground">
                  <Brain className="size-4 text-blue-400 shrink-0" />
                  <span className="text-[11px]">
                    <strong>Research Coordinator:</strong> Always executes as the synthesis node to validate data and produce the report.
                  </span>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* RIGHT COLUMN: Execution Workflow & Results (7 cols on lg) */}
          <div className="lg:col-span-7 space-y-6">
            {/* Panel 3: Execution Progress Tracker */}
            <Card className="border-border/80 bg-card/60 backdrop-blur shadow-sm">
              <CardHeader className="pb-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Activity className="size-4 text-primary" />
                    3. Execution Workflow
                  </CardTitle>

                  {executionResult && (
                    <div className="flex items-center gap-2 text-xs">
                      {getStatusBadge(executionResult.status)}
                      {executionResult.execution_time_seconds !== undefined && (
                        <span className="text-muted-foreground font-mono text-[11px] flex items-center gap-1">
                          <Clock className="size-3" />
                          {executionResult.execution_time_seconds}s
                        </span>
                      )}
                    </div>
                  )}
                </div>
                <CardDescription className="text-xs">
                  {isRunning
                    ? 'Processing LangGraph state channels across specialist nodes...'
                    : executionResult
                    ? `Execution ${executionResult.run_id ? `(ID: ${executionResult.run_id.slice(0, 8)})` : ''} completed.`
                    : 'Awaiting execution. Launch analysis to observe real-time workflow statuses.'}
                </CardDescription>
              </CardHeader>

              <CardContent className="pt-0">
                {/* Visual Pipeline Bar */}
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2 text-xs">
                  {[
                    { key: 'market_analyst', label: 'Market' },
                    { key: 'fundamental_analyst', label: 'Fundamentals' },
                    { key: 'news_analyst', label: 'News' },
                    { key: 'risk_analyst', label: 'Risk' },
                    { key: 'ml_analyst', label: 'ML' },
                    { key: 'coordinator', label: 'Coordinator' },
                  ].map((node) => {
                    const status = executionResult?.execution_statuses?.[node.key] || (isRunning ? 'running' : 'pending');
                    const isSkipped = status === 'skipped';
                    const isFailed = status === 'failed';
                    const isCompleted = status === 'completed';

                    return (
                      <div
                        key={node.key}
                        className={`p-2 rounded border flex flex-col items-center justify-center text-center transition-all ${
                          isCompleted
                            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                            : isFailed
                            ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                            : isSkipped
                            ? 'bg-muted/20 border-border/40 text-muted-foreground opacity-50'
                            : isRunning
                            ? 'bg-blue-500/10 border-blue-500/30 text-blue-300 animate-pulse'
                            : 'bg-muted/10 border-border/40 text-muted-foreground'
                        }`}
                      >
                        <div className="mb-1">{AGENT_ICON_MAP[node.key]}</div>
                        <span className="font-semibold text-[11px]">{node.label}</span>
                        <span className="text-[9px] capitalize mt-0.5">
                          {executionResult ? status : 'Pending'}
                        </span>
                      </div>
                    );
                  })}
                </div>

                {/* Run Metadata Footer */}
                {executionResult && (
                  <div className="mt-3 pt-3 border-t border-border/40 flex flex-wrap items-center justify-between gap-3 text-[11px] text-muted-foreground">
                    <div className="flex items-center gap-3">
                      <span>
                        Tickers: <strong className="text-foreground">{executionResult.tickers.join(', ') || 'N/A'}</strong>
                      </span>
                      <span>•</span>
                      <span>
                        Scope: <strong className="text-foreground uppercase">{executionResult.scope}</strong>
                      </span>
                      <span>•</span>
                      <span>
                        Provider: <strong className="text-foreground">{executionResult.llm_provider_used || 'Hybrid'}</strong>
                      </span>
                    </div>

                    <div>
                      {executionResult.completed_at && (
                        <span>
                          {new Date(executionResult.completed_at).toLocaleTimeString('en-IN', {
                            hour: '2-digit',
                            minute: '2-digit',
                            second: '2-digit',
                          })}
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Panel 4 & 5: Results Viewer (Consolidated Report & Specialists Tabs) */}
            {executionResult ? (
              <Card className="border-border/80 bg-card/60 backdrop-blur shadow-sm overflow-hidden">
                {/* View Mode Tabs */}
                <div className="border-b border-border/80 flex items-center justify-between px-4 bg-muted/20">
                  <div className="flex gap-1 text-xs">
                    <button
                      onClick={() => setActiveTab('report')}
                      className={`px-4 py-3 font-semibold border-b-2 transition-all flex items-center gap-2 ${
                        activeTab === 'report'
                          ? 'border-primary text-primary bg-background/60'
                          : 'border-transparent text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      <FileText className="size-3.5" />
                      Consolidated Report
                    </button>

                    <button
                      onClick={() => setActiveTab('specialists')}
                      className={`px-4 py-3 font-semibold border-b-2 transition-all flex items-center gap-2 ${
                        activeTab === 'specialists'
                          ? 'border-primary text-primary bg-background/60'
                          : 'border-transparent text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      <Brain className="size-3.5" />
                      Individual Specialist Findings
                      <Badge variant="outline" className="ml-1 text-[10px] scale-90">
                        {Object.keys(executionResult.agent_results || {}).length}
                      </Badge>
                    </button>

                    <button
                      onClick={() => setActiveTab('evidence')}
                      className={`px-4 py-3 font-semibold border-b-2 transition-all flex items-center gap-2 ${
                        activeTab === 'evidence'
                          ? 'border-primary text-primary bg-background/60'
                          : 'border-transparent text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      <Database className="size-3.5" />
                      Evidence & Sources
                    </button>
                  </div>
                </div>

                <CardContent className="p-6">
                  {/* TAB 1: Consolidated Report */}
                  {activeTab === 'report' && (
                    <div className="space-y-6">
                      {executionResult.final_report ? (
                        <div className="prose prose-invert prose-slate max-w-none prose-headings:text-foreground prose-headings:font-bold prose-h1:text-xl prose-h2:text-lg prose-h2:border-b prose-h2:border-border/60 prose-h2:pb-2 prose-h2:mt-6 prose-p:text-muted-foreground prose-p:leading-relaxed prose-li:text-muted-foreground prose-strong:text-foreground prose-blockquote:border-l-primary prose-blockquote:bg-muted/20 prose-blockquote:py-1 prose-blockquote:px-4 prose-blockquote:rounded-r text-sm">
                          <ReactMarkdown>{executionResult.final_report}</ReactMarkdown>
                        </div>
                      ) : (
                        <div className="text-center py-12 text-muted-foreground text-sm">
                          No consolidated report generated for this run.
                        </div>
                      )}
                    </div>
                  )}

                  {/* TAB 2: Individual Specialist Findings */}
                  {activeTab === 'specialists' && (
                    <div className="space-y-4">
                      {DEFAULT_AGENTS.map((agent) => {
                        const result: AgentResultDetail | undefined =
                          executionResult.agent_results?.[agent.name];
                        const isExpanded = expandedSpecialist === agent.name;

                        if (!result) {
                          return (
                            <div
                              key={agent.name}
                              className="p-3 rounded-lg border border-border/40 bg-muted/10 flex items-center justify-between text-xs text-muted-foreground"
                            >
                              <div className="flex items-center gap-2">
                                {AGENT_ICON_MAP[agent.name]}
                                <span>{agent.display_name}</span>
                              </div>
                              <Badge variant="outline" className="opacity-50 text-[10px]">
                                Not Selected
                              </Badge>
                            </div>
                          );
                        }

                        return (
                          <div
                            key={agent.name}
                            className="rounded-lg border border-border bg-card overflow-hidden shadow-xs"
                          >
                            {/* Header row */}
                            <div
                              onClick={() => setExpandedSpecialist(isExpanded ? null : agent.name)}
                              className="p-3.5 flex items-center justify-between gap-3 cursor-pointer hover:bg-muted/30 transition-colors"
                            >
                              <div className="flex items-center gap-2.5">
                                <div className="p-1.5 rounded bg-muted">
                                  {AGENT_ICON_MAP[agent.name]}
                                </div>
                                <div>
                                  <span className="font-semibold text-sm text-foreground">
                                    {agent.display_name}
                                  </span>
                                  <p className="text-[11px] text-muted-foreground line-clamp-1">
                                    {result.summary || 'Click to view findings and verified metrics.'}
                                  </p>
                                </div>
                              </div>

                              <div className="flex items-center gap-2 shrink-0">
                                {getStatusBadge(result.status)}
                                {getConfidenceBadge(result.confidence)}
                                {isExpanded ? (
                                  <ChevronDown className="size-4 text-muted-foreground" />
                                ) : (
                                  <ChevronRight className="size-4 text-muted-foreground" />
                                )}
                              </div>
                            </div>

                            {/* Expandable detail body */}
                            {isExpanded && (
                              <div className="p-4 pt-1 border-t border-border/60 bg-muted/5 text-xs space-y-4">
                                {/* Summary */}
                                {result.summary && (
                                  <div>
                                    <h4 className="text-xs font-semibold text-foreground mb-1">Summary</h4>
                                    <p className="text-muted-foreground leading-relaxed">
                                      {result.summary}
                                    </p>
                                  </div>
                                )}

                                {/* Key Findings */}
                                {result.key_findings && result.key_findings.length > 0 && (
                                  <div>
                                    <h4 className="text-xs font-semibold text-foreground mb-1.5">
                                      Key Grounded Findings
                                    </h4>
                                    <ul className="space-y-1 list-disc list-inside text-muted-foreground">
                                      {result.key_findings.map((f, idx) => (
                                        <li key={idx} className="leading-snug">
                                          <span className="text-foreground">{f}</span>
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                )}

                                {/* Supporting Metrics Grid */}
                                {result.supporting_metrics &&
                                  Object.keys(result.supporting_metrics).length > 0 && (
                                    <div>
                                      <h4 className="text-xs font-semibold text-foreground mb-2">
                                        Supporting Verified Metrics
                                      </h4>
                                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                                        {Object.entries(result.supporting_metrics).map(([k, v]) => {
                                          if (typeof v === 'object' && v !== null) {
                                            return (
                                              <div
                                                key={k}
                                                className="col-span-2 sm:col-span-3 p-2 rounded bg-muted/40 border border-border/60 font-mono text-[11px]"
                                              >
                                                <strong className="text-foreground block mb-1">{k}:</strong>
                                                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                                                  {Object.entries(v).map(([subK, subV]) => (
                                                    <div key={subK} className="p-1">
                                                      <span className="text-muted-foreground block text-[10px]">
                                                        {subK}
                                                      </span>
                                                      <span className="text-foreground font-semibold">
                                                        {formatINRValue(subV)}
                                                      </span>
                                                    </div>
                                                  ))}
                                                </div>
                                              </div>
                                            );
                                          }

                                          return (
                                            <div
                                              key={k}
                                              className="p-2 rounded bg-muted/30 border border-border/40 font-mono"
                                            >
                                              <span className="text-[10px] text-muted-foreground block truncate">
                                                {k}
                                              </span>
                                              <span className="text-foreground font-semibold text-xs">
                                                {formatINRValue(v)}
                                              </span>
                                            </div>
                                          );
                                        })}
                                      </div>
                                    </div>
                                  )}

                                {/* Warnings or Limitations */}
                                {result.warnings && result.warnings.length > 0 && (
                                  <div className="p-3 rounded bg-amber-500/10 border border-amber-500/30 text-amber-300">
                                    <strong className="block text-[11px] mb-1">Warnings & Caveats:</strong>
                                    <ul className="list-disc list-inside space-y-0.5 text-[11px]">
                                      {result.warnings.map((w, idx) => (
                                        <li key={idx}>{w}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}

                                {/* Missing Information */}
                                {result.missing_information && result.missing_information.length > 0 && (
                                  <div className="p-3 rounded bg-muted/40 border border-border/60 text-muted-foreground">
                                    <strong className="block text-[11px] text-foreground mb-1">
                                      Data Gaps & Missing Information:
                                    </strong>
                                    <ul className="list-disc list-inside space-y-0.5 text-[11px]">
                                      {result.missing_information.map((m, idx) => (
                                        <li key={idx}>{m}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}

                                {/* Error detail if failed */}
                                {result.error_message && (
                                  <div className="p-3 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300">
                                    <strong className="block text-[11px] mb-0.5">Failure Reason:</strong>
                                    <span>{result.error_message}</span>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* TAB 3: Evidence & Sources */}
                  {activeTab === 'evidence' && (
                    <div className="space-y-4 text-xs">
                      <div>
                        <h4 className="font-semibold text-foreground mb-2">Aggregated Data Sources</h4>
                        {executionResult.evidence_sources && executionResult.evidence_sources.length > 0 ? (
                          <div className="flex flex-wrap gap-2">
                            {executionResult.evidence_sources.map((src) => (
                              <Badge
                                key={src}
                                variant="outline"
                                className="px-2.5 py-1 text-xs font-mono bg-muted/30 border-border"
                              >
                                <Database className="size-3 mr-1 text-primary" />
                                {src}
                              </Badge>
                            ))}
                          </div>
                        ) : (
                          <p className="text-muted-foreground">No specific evidence sources recorded.</p>
                        )}
                      </div>

                      <Separator className="my-4" />

                      <div>
                        <h4 className="font-semibold text-foreground mb-2">System Limitations & Scope Notice</h4>
                        <p className="text-muted-foreground leading-relaxed">
                          All analysis is generated deterministically from historical market data, fundamental financial
                          statements, and news sentiment records stored in the ArthAI database. Technical signals and ML
                          predictions represent probabilistic estimates and historical performance indicators, not future
                          guarantees.
                        </p>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            ) : (
              /* Empty state placeholder when no analysis has run */
              <Card className="border-dashed border-border/80 bg-card/30 backdrop-blur py-16 text-center shadow-none">
                <CardContent className="space-y-3 flex flex-col items-center justify-center max-w-md mx-auto">
                  <div className="p-4 rounded-full bg-primary/10 border border-primary/20 text-primary">
                    <Sparkles className="size-8" />
                  </div>
                  <h3 className="font-bold text-lg text-foreground">Multi-Agent Intelligence Ready</h3>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Select a stock ticker or enter a natural-language research question on the left to launch the
                    LangGraph multi-agent workflow. The coordinator will dispatch tasks to Market, Fundamental, News,
                    ML, and Risk specialist agents and synthesise a grounded research report.
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setTickerInput('INFY');
                      setScope('standard');
                    }}
                    className="mt-2 text-xs gap-1.5"
                  >
                    Load Sample (Infosys / INFY)
                    <ArrowRight className="size-3" />
                  </Button>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
