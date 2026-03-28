/**
 * SyncButton – triggers a manual email sync.
 *
 * Props:
 *   onSync      – async callback (calls POST /api/sync)
 *   isSyncing   – true while the mutation is in-flight
 *   lastSyncAt  – ISO string or null from /api/me or /api/stats/summary
 */

import { RefreshCw, Loader2 } from "lucide-react";

interface SyncButtonProps {
  onSync: () => void;
  isSyncing: boolean;
  lastSyncAt: string | null | undefined;
}

function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return new Date(iso).toLocaleDateString();
}

export function SyncButton({ onSync, isSyncing, lastSyncAt }: SyncButtonProps) {
  return (
    <div className="flex flex-col items-end gap-1">
      <button
        onClick={onSync}
        disabled={isSyncing}
        className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500
                   disabled:opacity-50 disabled:cursor-not-allowed
                   text-white text-sm font-semibold rounded-lg
                   transition-all duration-150 shadow-sm"
      >
        {isSyncing ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <RefreshCw className="w-4 h-4" />
        )}
        {isSyncing ? "Syncing…" : "Sync Now"}
      </button>
      {lastSyncAt && (
        <span className="text-xs text-slate-500">
          Last sync: {formatRelative(lastSyncAt)}
        </span>
      )}
    </div>
  );
}
