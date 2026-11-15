'use client';

import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export default function AssistantPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!input.trim()) return;

    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${apiBaseUrl}/assistant/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question: input,
        }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const data = await response.json();

      // Add assistant response
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.answer || 'No response received',
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to get response';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 p-8">
      <div className="max-w-4xl mx-auto h-screen flex flex-col">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-4xl font-bold text-white mb-2">Investment Assistant</h1>
          <p className="text-slate-400">
            Ask questions about stocks, analysis, investment strategies, and more
          </p>
        </div>

        {/* Chat Container */}
        <div className="flex-1 bg-slate-800 rounded-lg border border-slate-700 p-6 overflow-y-auto mb-6 flex flex-col">
          {messages.length === 0 && !error && (
            <div className="flex-1 flex flex-col items-center justify-center text-center">
              <div className="text-6xl mb-4">💬</div>
              <h2 className="text-2xl font-semibold text-slate-300 mb-2">Start Your Conversation</h2>
              <p className="text-slate-400 max-w-md">
                Ask me anything about stock analysis, investment strategies, technical indicators, or
                company fundamentals. I'll provide detailed explanations with relevant data.
              </p>
            </div>
          )}

          {error && (
            <div className="mb-4 p-4 bg-red-900/20 border border-red-700 rounded text-red-200">
              <p className="font-semibold">Error</p>
              <p>{error}</p>
            </div>
          )}

          <div className="space-y-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-xl px-4 py-3 rounded-lg ${
                    message.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-700 text-slate-100 border border-slate-600'
                  }`}
                >
                  {message.role === 'assistant' ? (
                    <div className="prose prose-invert max-w-none">
                      <ReactMarkdown>{message.content}</ReactMarkdown>
                    </div>
                  ) : (
                    <p>{message.content}</p>
                  )}
                  <p
                    className={`text-xs mt-2 ${
                      message.role === 'user' ? 'text-blue-100' : 'text-slate-400'
                    }`}
                  >
                    {message.timestamp.toLocaleTimeString()}
                  </p>
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-slate-700 text-slate-100 border border-slate-600 px-4 py-3 rounded-lg">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                    <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div ref={messagesEndRef} />
        </div>

        {/* Input Section */}
        <form onSubmit={handleSendMessage} className="bg-slate-800 rounded-lg border border-slate-700 p-4">
          <div className="flex gap-3 mb-3">
            <input
              type="text"
              placeholder="Ask something about Indian stocks, analysis, investment strategy..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
              className="flex-1 px-4 py-2 bg-slate-700 text-white rounded border border-slate-600 focus:outline-none focus:border-blue-500 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {loading ? 'Thinking...' : 'Send'}
            </button>
            {messages.length > 0 && (
              <button
                type="button"
                onClick={handleClearChat}
                disabled={loading}
                className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded font-semibold disabled:opacity-50 transition"
              >
                Clear
              </button>
            )}
          </div>
        </form>

        {/* Disclaimer */}
        <div className="mt-4 p-3 bg-yellow-900/20 border border-yellow-700 rounded text-yellow-100 text-xs">
          <p className="font-semibold">⚠️ Disclaimer</p>
          <p>
            Responses are AI-generated and not professional financial advice. Always verify information with official sources
            and conduct thorough research before making investment decisions.
          </p>
        </div>
      </div>
    </div>
  );
}
