"use client";

/**
 * app/error.tsx – Next.js App Router error boundary.
 *
 * Catches unhandled runtime errors and shows a friendly recovery UI
 * instead of a blank page.
 */

import { useEffect } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log to console in development; swap for a real error service in production
    console.error("[App Error]", error);
  }, [error]);

  return (
    <div className="min-h-screen bg-slate-950 text-white flex flex-col items-center justify-center px-6 text-center gap-6">
      <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
        <AlertTriangle className="w-8 h-8 text-red-400" />
      </div>

      <div className="space-y-2 max-w-sm">
        <h1 className="text-xl font-bold">Something went wrong</h1>
        <p className="text-slate-400 text-sm">
          An unexpected error occurred. You can try refreshing the page or go
          back to the home screen.
        </p>
        {error.digest && (
          <p className="text-slate-600 text-xs font-mono">
            Error ID: {error.digest}
          </p>
        )}
      </div>

      <div className="flex gap-3">
        <button
          onClick={reset}
          className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500
                     text-white text-sm font-semibold rounded-lg transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Try again
        </button>
        <a
          href="/"
          className="flex items-center gap-2 px-5 py-2.5 border border-slate-700
                     hover:bg-slate-800 text-slate-300 text-sm font-semibold rounded-lg
                     transition-colors"
        >
          Go home
        </a>
      </div>
    </div>
  );
}
