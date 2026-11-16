'use client';

import { useState } from 'react';
import {
  useMlPredictionExplanation,
  useTechnicalSignalExplanation,
  useFundamentalScoreExplanation,
  useNewsSentimentExplanation,
} from '@/hooks/useExplanations';
import ReactMarkdown from 'react-markdown';

export default function ExplanationsPage() {
  const [ticker, setTicker] = useState('');
  const [activeTab, setActiveTab] = useState<'ml' | 'signal' | 'score' | 'sentiment'>('ml');

  const mlPrediction = useMlPredictionExplanation();
  const technicalSignal = useTechnicalSignalExplanation();
  const fundamentalScore = useFundamentalScoreExplanation();
  const newsSentiment = useNewsSentimentExplanation();

  const handleExplainML = async () => {
    if (ticker.trim()) {
      await mlPrediction.explain(ticker);
    }
  };

  const handleExplainSignal = async () => {
    if (ticker.trim()) {
      await technicalSignal.explain(ticker);
    }
  };

  const handleExplainScore = async () => {
    if (ticker.trim()) {
      await fundamentalScore.explain(ticker);
    }
  };

  const handleExplainSentiment = async () => {
    if (ticker.trim()) {
      await newsSentiment.explain(ticker);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">AI Explanations</h1>
          <p className="text-slate-400">
            Understand ML predictions, technical signals, fundamental scores, and sentiment analysis
          </p>
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
                if (e.key === 'Enter') handleExplainML();
              }}
              className="flex-1 px-4 py-2 bg-slate-700 text-white rounded border border-slate-600 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Action Buttons */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <button
              onClick={handleExplainML}
              disabled={!ticker || mlPrediction.loading}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition text-sm"
            >
              {mlPrediction.loading ? 'Explaining...' : 'ML Prediction'}
            </button>
            <button
              onClick={handleExplainSignal}
              disabled={!ticker || technicalSignal.loading}
              className="px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition text-sm"
            >
              {technicalSignal.loading ? 'Explaining...' : 'Technical Signal'}
            </button>
            <button
              onClick={handleExplainScore}
              disabled={!ticker || fundamentalScore.loading}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition text-sm"
            >
              {fundamentalScore.loading ? 'Explaining...' : 'Fundamental Score'}
            </button>
            <button
              onClick={handleExplainSentiment}
              disabled={!ticker || newsSentiment.loading}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition text-sm"
            >
              {newsSentiment.loading ? 'Explaining...' : 'News Sentiment'}
            </button>
          </div>
        </div>

        {/* Results Section */}
        <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
          {/* Tabs */}
          <div className="flex border-b border-slate-700 overflow-x-auto">
            <button
              onClick={() => setActiveTab('ml')}
              className={`px-4 py-3 text-sm font-semibold transition whitespace-nowrap ${
                activeTab === 'ml'
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              ML Prediction
            </button>
            <button
              onClick={() => setActiveTab('signal')}
              className={`px-4 py-3 text-sm font-semibold transition whitespace-nowrap ${
                activeTab === 'signal'
                  ? 'bg-cyan-600 text-white'
                  : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              Technical Signal
            </button>
            <button
              onClick={() => setActiveTab('score')}
              className={`px-4 py-3 text-sm font-semibold transition whitespace-nowrap ${
                activeTab === 'score'
                  ? 'bg-indigo-600 text-white'
                  : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              Fundamental Score
            </button>
            <button
              onClick={() => setActiveTab('sentiment')}
              className={`px-4 py-3 text-sm font-semibold transition whitespace-nowrap ${
                activeTab === 'sentiment'
                  ? 'bg-emerald-600 text-white'
                  : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              News Sentiment
            </button>
          </div>

          {/* Content */}
          <div className="p-6 max-h-96 overflow-y-auto">
            {activeTab === 'ml' && (
              <div>
                {mlPrediction.error && (
                  <div className="text-red-400 mb-4">{mlPrediction.error}</div>
                )}
                {mlPrediction.explanation && (
                  <div className="prose prose-invert max-w-none text-slate-300">
                    <ReactMarkdown>{mlPrediction.explanation}</ReactMarkdown>
                  </div>
                )}
                {!mlPrediction.explanation && !mlPrediction.error && !mlPrediction.loading && (
                  <div className="text-slate-500 text-center py-8">
                    Enter a ticker and click "ML Prediction" to get started
                  </div>
                )}
              </div>
            )}

            {activeTab === 'signal' && (
              <div>
                {technicalSignal.error && (
                  <div className="text-red-400 mb-4">{technicalSignal.error}</div>
                )}
                {technicalSignal.explanation && (
                  <div className="prose prose-invert max-w-none text-slate-300">
                    <ReactMarkdown>{technicalSignal.explanation}</ReactMarkdown>
                  </div>
                )}
                {!technicalSignal.explanation && !technicalSignal.error && !technicalSignal.loading && (
                  <div className="text-slate-500 text-center py-8">
                    Enter a ticker and click "Technical Signal" to get started
                  </div>
                )}
              </div>
            )}

            {activeTab === 'score' && (
              <div>
                {fundamentalScore.error && (
                  <div className="text-red-400 mb-4">{fundamentalScore.error}</div>
                )}
                {fundamentalScore.explanation && (
                  <div className="prose prose-invert max-w-none text-slate-300">
                    <ReactMarkdown>{fundamentalScore.explanation}</ReactMarkdown>
                  </div>
                )}
                {!fundamentalScore.explanation && !fundamentalScore.error && !fundamentalScore.loading && (
                  <div className="text-slate-500 text-center py-8">
                    Enter a ticker and click "Fundamental Score" to get started
                  </div>
                )}
              </div>
            )}

            {activeTab === 'sentiment' && (
              <div>
                {newsSentiment.error && (
                  <div className="text-red-400 mb-4">{newsSentiment.error}</div>
                )}
                {newsSentiment.explanation && (
                  <div className="prose prose-invert max-w-none text-slate-300">
                    <ReactMarkdown>{newsSentiment.explanation}</ReactMarkdown>
                  </div>
                )}
                {!newsSentiment.explanation && !newsSentiment.error && !newsSentiment.loading && (
                  <div className="text-slate-500 text-center py-8">
                    Enter a ticker and click "News Sentiment" to get started
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Disclaimer */}
        <div className="mt-8 p-4 bg-yellow-900/20 border border-yellow-700 rounded text-yellow-100 text-sm">
          <p className="font-semibold mb-2">⚠️ Disclaimer & Uncertainty</p>
          <p>
            All explanations are AI-generated and include uncertainty assessments. 
            These are interpretations of market signals, not guarantees. 
            Always verify with official sources and conduct your own research before making investment decisions.
          </p>
        </div>
      </div>
    </div>
  );
}
