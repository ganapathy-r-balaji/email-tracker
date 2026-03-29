"use client";

/**
 * app/dashboard/page.tsx – Full dashboard.
 *
 * Data flow (React Query):
 *   useQuery ["me"]            → auth guard + last_sync_at
 *   useQuery ["stats"]         → StatsBar
 *   useQuery ["orders", page, statusFilter] → order list
 *   useMutation syncApi.trigger → SyncButton; invalidates all queries on success
 */

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { Package, LogOut, ChevronLeft, ChevronRight, InboxIcon, TrendingUp, RotateCcw } from "lucide-react";
import Link from "next/link";
import { authApi, ordersApi, syncApi, accountsApi, is401 } from "@/lib/api";
import type { Order } from "@/lib/api";
import { StatsBar } from "@/components/StatsBar";
import { SyncButton } from "@/components/SyncButton";
import { OrderCard } from "@/components/OrderCard";
import { Toast, type ToastState } from "@/components/Toast";
import { ConnectedAccounts } from "@/components/ConnectedAccounts";

// ─── Status filter options ────────────────────────────────────────────────────
const STATUS_FILTERS = [
  { label: "All", value: "" },
  { label: "Ordered", value: "ordered" },
  { label: "Shipped", value: "shipped" },
  { label: "Delivered", value: "delivered" },
] as const;

type StatusFilter = "" | "ordered" | "shipped" | "delivered";

const PER_PAGE = 20;

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("");
  const [toast, setToast] = useState<ToastState | null>(null);

  // ── Show toast + clean URL when redirected back after adding an account ──
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("account_added") === "true") {
      setToast({ message: "Gmail account connected!", variant: "success" });
      const url = new URL(window.location.href);
      url.searchParams.delete("account_added");
      window.history.replaceState({}, "", url.toString());
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Auth + user ────────────────────────────────────────────────────────────
  const { data: user, isLoading: userLoading } = useQuery({
    queryKey: ["me"],
    queryFn: authApi.me,
    retry: (count, err) => {
      if (is401(err)) return false;
      return count < 2;
    },
  });

  // Redirect to landing if not authenticated
  const { isError: meError, error: meErr } = useQuery({
    queryKey: ["me"],
    queryFn: authApi.me,
  });
  if (meError && is401(meErr)) {
    router.replace("/");
  }

  // ── Connected Gmail accounts ───────────────────────────────────────────────
  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: accountsApi.list,
    enabled: !!user,
  });

  // ── Stats ──────────────────────────────────────────────────────────────────
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["stats"],
    queryFn: ordersApi.stats,
    enabled: !!user,
    refetchInterval: 60_000,
  });

  // ── Orders list ────────────────────────────────────────────────────────────
  const { data: ordersData, isLoading: ordersLoading } = useQuery({
    queryKey: ["orders", page, statusFilter],
    queryFn: () => ordersApi.list(page, PER_PAGE, statusFilter || undefined),
    enabled: !!user,
    refetchInterval: 60_000,
    placeholderData: (prev) => prev, // keep previous data while fetching new page
  });

  // ── Sync mutation ──────────────────────────────────────────────────────────
  const syncMutation = useMutation({
    mutationFn: syncApi.trigger,
    onSuccess: (data) => {
      setToast({ message: data.message, variant: "success" });
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["orders"] });
        queryClient.invalidateQueries({ queryKey: ["stats"] });
        queryClient.invalidateQueries({ queryKey: ["me"] });
      }, 8_000);
    },
    onError: () => {
      setToast({ message: "Sync failed. Please check your connection and try again.", variant: "error" });
    },
  });

  // ── Reset & re-sync mutation ───────────────────────────────────────────────
  const resetMutation = useMutation({
    mutationFn: syncApi.reset,
    onSuccess: (data) => {
      setToast({ message: data.message, variant: "success" });
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["orders"] });
        queryClient.invalidateQueries({ queryKey: ["stats"] });
        queryClient.invalidateQueries({ queryKey: ["me"] });
      }, 8_000);
    },
    onError: () => {
      setToast({ message: "Reset failed. Please try again.", variant: "error" });
    },
  });

  // ── Filter tab change ──────────────────────────────────────────────────────
  const handleFilterChange = (value: StatusFilter) => {
    setStatusFilter(value);
    setPage(1); // reset to page 1 on filter change
  };

  // ── Loading skeleton ───────────────────────────────────────────────────────
  const isInitialLoading = userLoading;

  const orders: Order[] = ordersData?.orders ?? [];
  const totalPages = ordersData?.pages ?? 1;

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-slate-950 text-white flex flex-col">
      <Toast toast={toast} onDismiss={() => setToast(null)} />
      {/* ── Navbar ─────────────────────────────────────────────────────────── */}
      <nav className="sticky top-0 z-10 px-4 sm:px-6 py-3 flex items-center justify-between
                      border-b border-slate-800 bg-slate-950/90 backdrop-blur">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <Package className="w-5 h-5 text-blue-400" />
            <span className="font-semibold tracking-tight">PackageTracker AI</span>
          </div>
          <Link
            href="/spending"
            className="flex items-center gap-1.5 text-slate-400 hover:text-white text-sm transition-colors"
          >
            <TrendingUp className="w-4 h-4" />
            <span className="hidden sm:inline">Spending</span>
          </Link>
        </div>
        <div className="flex items-center gap-4">
          {user && (
            <span className="text-slate-400 text-sm hidden sm:block truncate max-w-[200px]">
              {user.email}
            </span>
          )}
          <button
            onClick={authApi.logout}
            className="flex items-center gap-1.5 text-slate-400 hover:text-white text-sm transition-colors"
          >
            <LogOut className="w-4 h-4" />
            <span className="hidden sm:inline">Sign out</span>
          </button>
        </div>
      </nav>

      {/* ── Main content ───────────────────────────────────────────────────── */}
      <main className="flex-1 w-full max-w-4xl mx-auto px-4 sm:px-6 py-6 space-y-6">

        {isInitialLoading ? (
          <PageSkeleton />
        ) : (
          <>
            {/* Stats bar */}
            <StatsBar stats={stats} loading={statsLoading} />

            {/* Connected Gmail accounts panel */}
            <ConnectedAccounts
              accounts={accounts}
              onError={(msg) => setToast({ message: msg, variant: "error" })}
              onSuccess={(msg) => setToast({ message: msg, variant: "success" })}
            />

            {/* Toolbar: filter tabs + sync button */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              {/* Status filter tabs */}
              <div className="flex items-center gap-1 bg-slate-900 border border-slate-800 rounded-lg p-1">
                {STATUS_FILTERS.map((f) => (
                  <button
                    key={f.value}
                    onClick={() => handleFilterChange(f.value as StatusFilter)}
                    className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors duration-100
                      ${statusFilter === f.value
                        ? "bg-slate-700 text-white"
                        : "text-slate-400 hover:text-slate-200"
                      }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>

              {/* Sync + Reset buttons */}
              <div className="flex items-center gap-2">
                <SyncButton
                  onSync={() => syncMutation.mutate()}
                  isSyncing={syncMutation.isPending}
                  lastSyncAt={user?.last_sync_at ?? stats?.last_sync_at}
                />
                <button
                  onClick={() => {
                    if (confirm("This will clear all synced emails and re-process from scratch. Continue?")) {
                      resetMutation.mutate();
                    }
                  }}
                  disabled={resetMutation.isPending || syncMutation.isPending}
                  title="Clear all email logs and re-sync from scratch"
                  className="flex items-center gap-1.5 px-3 py-2 text-sm rounded-lg
                             border border-slate-700 text-slate-400 hover:text-white hover:border-slate-500
                             disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <RotateCcw className={`w-4 h-4 ${resetMutation.isPending ? "animate-spin" : ""}`} />
                  <span className="hidden sm:inline">Reset & Re-sync</span>
                </button>
              </div>
            </div>

            {/* Orders list */}
            {ordersLoading && orders.length === 0 ? (
              <OrdersSkeleton />
            ) : orders.length === 0 ? (
              <EmptyState hasFilter={!!statusFilter} />
            ) : (
              <div className="space-y-3">
                {orders.map((order) => (
                  <OrderCard key={order.id} order={order} />
                ))}
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-3 pt-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm rounded-lg
                             border border-slate-700 text-slate-300 hover:bg-slate-800
                             disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronLeft className="w-4 h-4" />
                  Prev
                </button>
                <span className="text-slate-400 text-sm">
                  Page {page} of {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm rounded-lg
                             border border-slate-700 text-slate-300 hover:bg-slate-800
                             disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  Next
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function EmptyState({ hasFilter }: { hasFilter: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
      <div className="w-16 h-16 rounded-2xl bg-slate-800 flex items-center justify-center">
        <InboxIcon className="w-8 h-8 text-slate-500" />
      </div>
      <div className="space-y-1">
        <p className="text-slate-300 font-medium">
          {hasFilter ? "No orders match this filter" : "No orders yet"}
        </p>
        <p className="text-slate-500 text-sm max-w-xs">
          {hasFilter
            ? "Try selecting a different status tab."
            : "Click Sync Now to scan your Gmail for order and shipment emails."}
        </p>
      </div>
    </div>
  );
}

function PageSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="grid grid-cols-3 gap-3 sm:gap-4">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-20 rounded-xl bg-slate-800" />
        ))}
      </div>
      <div className="h-10 rounded-lg bg-slate-800 w-64" />
      <OrdersSkeleton />
    </div>
  );
}

function OrdersSkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="h-24 rounded-xl bg-slate-800" />
      ))}
    </div>
  );
}
