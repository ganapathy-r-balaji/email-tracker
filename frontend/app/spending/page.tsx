"use client";

/**
 * app/spending/page.tsx – Spending analytics dashboard.
 *
 * Six charts driven by a single date range picker:
 *   1. By year-month       (time series bar)
 *   2. By month of year    (Jan–Dec aggregate bar)
 *   3. By week of month    (weeks 1–5 bar)
 *   4. By week of year     (W1–W52 bar)
 *   5. By product category (donut + legend)
 *   6. Top vendors         (ranked table)
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Package, LogOut, ArrowLeft, TrendingUp } from "lucide-react";
import Link from "next/link";

import { authApi, spendingApi, is401 } from "@/lib/api";
import { DateRangePicker } from "@/components/spending/DateRangePicker";
import { SpendingYearMonthChart } from "@/components/spending/SpendingYearMonthChart";
import { SpendingMonthOfYearChart } from "@/components/spending/SpendingMonthOfYearChart";
import { SpendingWeekOfMonthChart } from "@/components/spending/SpendingWeekOfMonthChart";
import { SpendingWeekOfYearChart } from "@/components/spending/SpendingWeekOfYearChart";
import { SpendingCategoryChart } from "@/components/spending/SpendingCategoryChart";
import { TopVendorsTable } from "@/components/spending/TopVendorsTable";

// ─── Default date range: last 12 months ───────────────────────────────────────
function defaultDates(): { start: string; end: string } {
  const end = new Date();
  const start = new Date(end);
  start.setFullYear(start.getFullYear() - 1);
  return {
    start: start.toISOString().split("T")[0],
    end: end.toISOString().split("T")[0],
  };
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function SpendingPage() {
  const router = useRouter();
  const defaults = defaultDates();

  const [startDate, setStartDate] = useState(defaults.start);
  const [endDate, setEndDate] = useState(defaults.end);

  // ── Auth guard ─────────────────────────────────────────────────────────────
  const { data: user, isError: meError, error: meErr } = useQuery({
    queryKey: ["me"],
    queryFn: authApi.me,
    retry: (count, err) => {
      if (is401(err)) return false;
      return count < 2;
    },
  });

  useEffect(() => {
    if (meError && is401(meErr)) {
      router.replace("/");
    }
  }, [meError, meErr, router]);

  // ── Spending data ──────────────────────────────────────────────────────────
  const { data: spending, isLoading } = useQuery({
    queryKey: ["spending", startDate, endDate],
    queryFn: () => spendingApi.stats(startDate, endDate),
    enabled: !!user,
    staleTime: 60_000,
  });

  const currency = spending?.primary_currency ?? "USD";

  function handleRangeChange(start: string, end: string) {
    setStartDate(start);
    setEndDate(end);
  }

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-slate-950 text-white flex flex-col">
      {/* ── Navbar ─────────────────────────────────────────────────────────── */}
      <nav className="sticky top-0 z-10 px-4 sm:px-6 py-3 flex items-center justify-between
                      border-b border-slate-800 bg-slate-950/90 backdrop-blur">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <Package className="w-5 h-5 text-blue-400" />
            <span className="font-semibold tracking-tight">PackageTracker AI</span>
          </div>
          <Link
            href="/dashboard"
            className="flex items-center gap-1.5 text-slate-400 hover:text-white text-sm transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="hidden sm:inline">Orders</span>
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
      <main className="flex-1 w-full max-w-5xl mx-auto px-4 sm:px-6 py-6 space-y-6">

        {/* Page header + date picker */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <TrendingUp className="w-5 h-5 text-blue-400" />
            <div>
              <h1 className="text-lg font-semibold">Spending Analysis</h1>
              {spending?.primary_currency && (
                <p className="text-xs text-slate-500">
                  Showing {spending.primary_currency} orders only
                </p>
              )}
            </div>
          </div>
          <DateRangePicker
            startDate={startDate}
            endDate={endDate}
            onChange={handleRangeChange}
          />
        </div>

        {/* ── No data state ────────────────────────────────────────────────── */}
        {!isLoading && spending && !spending.has_data ? (
          <div className="flex flex-col items-center justify-center py-24 gap-4 text-center">
            <div className="w-16 h-16 rounded-2xl bg-slate-800 flex items-center justify-center">
              <TrendingUp className="w-8 h-8 text-slate-500" />
            </div>
            <div className="space-y-1">
              <p className="text-slate-300 font-medium">No spending data for this period</p>
              <p className="text-slate-500 text-sm max-w-xs">
                Try selecting a wider date range, or sync your Gmail to import more orders.
              </p>
            </div>
            <Link
              href="/dashboard"
              className="mt-2 text-sm text-blue-400 hover:text-blue-300 transition-colors"
            >
              Go to Orders →
            </Link>
          </div>
        ) : (
          <>
            {/* Row 1: Year-month time series (full width) */}
            <SpendingYearMonthChart
              data={spending?.by_year_month ?? []}
              loading={isLoading}
              currency={currency}
            />

            {/* Row 2: Month-of-year + Week-of-month (side by side on md+) */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <SpendingMonthOfYearChart
                data={spending?.by_month_of_year ?? []}
                loading={isLoading}
                currency={currency}
              />
              <SpendingWeekOfMonthChart
                data={spending?.by_week_of_month ?? []}
                loading={isLoading}
                currency={currency}
              />
            </div>

            {/* Row 3: Week-of-year (full width) */}
            <SpendingWeekOfYearChart
              data={spending?.by_week_of_year ?? []}
              loading={isLoading}
              currency={currency}
            />

            {/* Row 4: Category donut + Top vendors (side by side on md+) */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <SpendingCategoryChart
                data={spending?.categories ?? []}
                loading={isLoading}
                currency={currency}
              />
              <TopVendorsTable
                data={spending?.top_vendors ?? []}
                loading={isLoading}
                currency={currency}
              />
            </div>
          </>
        )}
      </main>
    </div>
  );
}
