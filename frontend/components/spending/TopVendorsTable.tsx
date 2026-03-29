"use client";

import { TableSkeleton } from "./SpendingSkeletons";
import type { TopVendorEntry } from "@/lib/api";

interface Props {
  data: TopVendorEntry[];
  loading: boolean;
  currency: string;
}

function fmt(value: number, currency: string) {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(value);
}

export function TopVendorsTable({ data, loading, currency }: Props) {
  const maxSpend = data.length > 0 ? Math.max(...data.map((d) => d.total_spent)) : 1;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4 space-y-3">
      <h3 className="text-sm font-medium text-slate-300">Top Vendors</h3>

      {loading ? (
        <TableSkeleton rows={5} />
      ) : data.length === 0 ? (
        <p className="py-8 text-center text-slate-500 text-sm">No vendor data for this period</p>
      ) : (
        <div className="space-y-2">
          {data.map((row, i) => {
            const barWidth = maxSpend > 0 ? (row.total_spent / maxSpend) * 100 : 0;
            return (
              <div key={row.vendor} className="relative flex items-center gap-3 rounded-lg px-3 py-2.5 overflow-hidden">
                {/* Background progress bar */}
                <div
                  className="absolute inset-y-0 left-0 bg-blue-500/10 rounded-lg transition-all"
                  style={{ width: `${barWidth}%` }}
                />

                {/* Rank */}
                <span className="relative z-10 w-5 text-center text-xs font-medium text-slate-500 flex-shrink-0">
                  {i + 1}
                </span>

                {/* Vendor name */}
                <span className="relative z-10 flex-1 text-sm text-slate-200 font-medium truncate min-w-0">
                  {row.vendor}
                </span>

                {/* Order count */}
                <span className="relative z-10 text-xs text-slate-500 flex-shrink-0">
                  {row.order_count} {row.order_count === 1 ? "order" : "orders"}
                </span>

                {/* Total */}
                <span className="relative z-10 text-sm font-semibold text-slate-100 flex-shrink-0 tabular-nums">
                  {fmt(row.total_spent, currency)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
