
"use client";

import { useEffect, useState } from "react";
import { checkBackend } from "@/lib/api";

export default function Home() {
  const [backend, setBackend] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    checkBackend()
      .then((data) => setBackend(data))
      .catch(() => setError("Could not connect to ArthAI backend"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="min-h-screen flex flex-col items-center justify-center bg-slate-950 text-white p-8">
      <h1 className="text-4xl font-bold mb-4">
        ArthAI
      </h1>

      <p className="text-slate-400 mb-8">
        Agentic Financial Intelligence Platform
      </p>

      <div className="rounded-xl border border-slate-700 p-6 w-full max-w-md bg-slate-900">
        <h2 className="text-xl font-semibold mb-4">
          Backend Connection
        </h2>

        {loading && <p>Connecting to backend...</p>}

        {backend && (
          <div className="text-green-400">
            <p>✓ Backend connected successfully!</p>
            <p className="mt-2">Status: {backend.status}</p>
            <p>Application: {backend.application}</p>
          </div>
        )}

        {error && (
          <p className="text-red-400">{error}</p>
        )}
      </div>
    </main>
  );
}

