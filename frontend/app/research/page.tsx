'use client';

import { useState } from 'react';
import { useCompanyOverview, useSwotAnalysis, useResearchReport } from '@/hooks/useResearch';
import ReactMarkdown from 'react-markdown';

export default function ResearchPage() {
  const [ticker, setTicker] = useState('');
  const [activeTab, setActiveTab] = useState<'overview' | 'swot' | 'report'>('overview');

  const overview = useCompanyOverview();
  const swot = useSwotAnalysis();
  const report = useResearchReport();

  const handleGenerateOverview = async () => {
    if (ticker.trim()) {
      await overview.generate(ticker);
    }
  };

  const handleGenerateSwot = async () => {
    if (ticker.trim()) {
      await swot.generate(ticker);
    }
  };

  const handleGenerateReport = async () => {
    if (ticker.trim()) {
      await report.generate(ticker);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">Company Research</h1>
          <p className="text-slate-400">Generate comprehensive research on Indian stocks</p>
        </div>

        {/* Input Section */}
        <div className="bg-slate-800 rounded-lg p-6 mb-8 border border-slate-700">
          <div className="flex gap-4 mb-6">
            <input
              type="text"
              placeholder="Enter stock ticker (e.g., TCS, INFY, HDFC)"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              onKeyPress={(e) => {
                if (e.key === 'Enter') handleGenerateOverview();
              }}
              className="flex-1 px-4 py-2 bg-slate-700 text-white rounded border border-slate-600 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Action Buttons */}
          <div className="grid grid-cols-3 gap-4">
            <button
              onClick={handleGenerateOverview}
              disabled={!ticker || overview.loading}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {overview.loading ? 'Generating...' : 'Company Overview'}
            </button>
            <button
              onClick={handleGenerateSwot}
              disabled={!ticker || swot.loading}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {swot.loading ? 'Generating...' : 'SWOT Analysis'}
            </button>
            <button
              onClick={handleGenerateReport}
              disabled={!ticker || report.loading}
              className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {report.loading ? 'Generating...' : 'Full Report'}
            </button>
          </div>
        </div>

        {/* Results Section */}
        <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
          {/* Tabs */}
          <div className="flex border-b border-slate-700">
            <button
              onClick={() => setActiveTab('overview')}
              className={`flex-1 px-4 py-3 text-sm font-semibold transition ${
                activeTab === 'overview'
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              Overview
            </button>
            <button
              onClick={() => setActiveTab('swot')}
              className={`flex-1 px-4 py-3 text-sm font-semibold transition ${
                activeTab === 'swot'
                  ? 'bg-purple-600 text-white'
                  : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              SWOT
            </button>
            <button
              onClick={() => setActiveTab('report')}
              className={`flex-1 px-4 py-3 text-sm font-semibold transition ${
                activeTab === 'report'
                  ? 'bg-green-600 text-white'
                  : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              Report
            </button>
          </div>

          {/* Content */}
          <div className="p-6">
            {activeTab === 'overview' && (
              <div>
                {overview.error && (
                  <div className="text-red-400 mb-4">{overview.error}</div>
                )}
                {overview.data?.overview && (
                  <div className="prose prose-invert max-w-none text-slate-300">
                    <ReactMarkdown>{overview.data.overview}</ReactMarkdown>
                  </div>
                )}
                {!overview.data && !overview.error && !overview.loading && (
                  <div className="text-slate-500 text-center py-8">
                    Enter a ticker and click "Company Overview" to get started
                  </div>
                )}
              </div>
            )}

            {activeTab === 'swot' && (
              <div>
                {swot.error && (
                  <div className="text-red-400 mb-4">{swot.error}</div>
                )}
                {swot.data?.swot && (
                  <div className="prose prose-invert max-w-none text-slate-300">
                    <ReactMarkdown>{swot.data.swot}</ReactMarkdown>
                  </div>
                )}
                {!swot.data && !swot.error && !swot.loading && (
                  <div className="text-slate-500 text-center py-8">
                    Enter a ticker and click "SWOT Analysis" to get started
                  </div>
                )}
              </div>
            )}

            {activeTab === 'report' && (
              <div>
                {report.error && (
                  <div className="text-red-400 mb-4">{report.error}</div>
                )}
                {report.data?.report && (
                  <div className="prose prose-invert max-w-none text-slate-300 max-h-96 overflow-y-auto">
                    <ReactMarkdown>{report.data.report}</ReactMarkdown>
                  </div>
                )}
                {!report.data && !report.error && !report.loading && (
                  <div className="text-slate-500 text-center py-8">
                    Enter a ticker and click "Full Report" to get started
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Disclaimer */}
        <div className="mt-8 p-4 bg-yellow-900/20 border border-yellow-700 rounded text-yellow-100 text-sm">
          <p className="font-semibold mb-2">⚠️ Disclaimer</p>
          <p>
            All analyses are generated by AI and should be verified with official sources. 
            This is not financial advice. Always conduct your own research before making investment decisions.
          </p>
        </div>
      </div>
    </div>
  );
}
