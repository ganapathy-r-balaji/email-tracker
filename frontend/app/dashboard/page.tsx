"use client";

/**
 * app/dashboard/page.tsx – Placeholder dashboard.
 * Full implementation comes in Step 8.
 *
 * For now: verifies auth is working and shows a "coming soon" message
 * with the user's email and a Sync button so you can test the full OAuth
 * → sync flow end-to-end tonight.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authApi, syncApi, is401, CurrentUser } from "@/lib/api";
import { Package, LogOut, RefreshCw, Loader2 } from "lucide-react";

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);

  // ── Auth check on mount ────────────────────────────────────────────────────
  useEffect(() => {
    authApi
      .me()
      .then((u) => {
        setUser(u);
        setLoading(false);
      })
      .catch((err) => {
        if (is401(err)) router.replace("/");
        else setLoading(false);
      });
  }, [router]);

  // ── Sync handler ──────────────────────────────────────────────────────────
  const handleSync = async () => {
    setSyncing(true);
    setSyncMsg(null);
    try {
      const res = await syncApi.trigger();
      setSyncMsg(res.message);
    } catch {
      setSyncMsg("Sync failed. Please try again.");
    } finally {
      setSyncing(false);
    }
  };

  // ── Loading ───────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950">
        <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
      </div>
    );
  }

  // ── Dashboard skeleton ────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-slate-950 text-white flex flex-col">
      {/* Nav */}
      <nav className="px-6 py-4 flex items-center justify-between border-b border-slate-800">
        <div className="flex items-center gap-3">
          <Package className="w-6 h-6 text-blue-400" />
          <span className="font-semibold text-lg tracking-tight">
            PackageTracker AI
          </span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-slate-400 text-sm hidden sm:block">
            {user?.email}
          </span>
          <button
            onClick={authApi.logout}
            className="flex items-center gap-1.5 text-slate-400 hover:text-white text-sm transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Sign out
          </button>
        </div>
      </nav>

      {/* Body */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 py-20 gap-8 text-center">
        <div className="space-y-3">
          <p className="text-slate-400 text-sm">Signed in as</p>
          <p className="text-white font-medium text-lg">{user?.email}</p>
          {user?.last_sync_at ? (
            <p className="text-slate-500 text-xs">
              Last synced:{" "}
              {new Date(user.last_sync_at).toLocaleString()}
            </p>
          ) : (
            <p className="text-slate-500 text-xs">No sync yet</p>
          )}
        </div>

        <div className="max-w-md space-y-2">
          <h1 className="text-2xl font-bold">
            You&apos;re connected! 🎉
          </h1>
          <p className="text-slate-400">
            Click <strong>Sync Now</strong> to scan your Gmail for order and
            shipment emails. The full dashboard is coming in Step 8.
          </p>
        </div>

        {/* Sync button */}
        <button
          onClick={handleSync}
          disabled={syncing}
          className="flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-500
                     disabled:opacity-50 disabled:cursor-not-allowed
                     text-white font-semibold rounded-xl transition-all duration-150"
        >
          {syncing ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <RefreshCw className="w-4 h-4" />
          )}
          {syncing ? "Starting sync…" : "Sync Now"}
        </button>

        {syncMsg && (
          <p className="text-emerald-400 text-sm">{syncMsg}</p>
        )}
      </main>
    </div>
  );
}
