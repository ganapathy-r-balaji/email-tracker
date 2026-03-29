"use client";

import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from "recharts";
import { ChartSkeleton } from "./SpendingSkeletons";
import type { CategoryEntry } from "@/lib/api";

const COLORS = [
  "#3b82f6", // blue-500
  "#a78bfa", // violet-400
  "#34d399", // emerald-400
  "#fbbf24", // amber-400
  "#f87171", // red-400
  "#22d3ee", // cyan-400
  "#fb923c", // orange-400
  "#e879f9", // fuchsia-400
];

interface Props {
  data: CategoryEntry[];
  loading: boolean;
  currency: string;
}

function fmt(value: number, currency: string) {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

export function SpendingCategoryChart({ data, loading, currency }: Props) {
  const hasData = data.some((d) => d.total > 0);

  // Cap at 8 slices; collapse the rest into "Other"
  let chartData = data.filter((d) => d.total > 0);
  if (chartData.length > 8) {
    const top = chartData.slice(0, 7);
    const otherTotal = chartData.slice(7).reduce((s, d) => s + d.total, 0);
    const otherCount = chartData.slice(7).reduce((s, d) => s + d.order_count, 0);
    chartData = [...top, { category: "Other", total: otherTotal, order_count: otherCount }];
  }

  const totalSpend = chartData.reduce((s, d) => s + d.total, 0);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4 space-y-3">
      <h3 className="text-sm font-medium text-slate-300">Spending by Category</h3>
      {loading ? (
        <ChartSkeleton />
      ) : !hasData ? (
        <EmptyChart />
      ) : (
        <div className="flex flex-col gap-4">
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie
                data={chartData}
                dataKey="total"
                nameKey="category"
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                paddingAngle={2}
              >
                {chartData.map((_, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={COLORS[index % COLORS.length]}
                  />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "#0f172a",
                  border: "1px solid #1e293b",
                  borderRadius: 8,
                  color: "#e2e8f0",
                }}
                formatter={(value, name) => [
                  fmt(Number(value), currency),
                  String(name),
                ]}
              />
            </PieChart>
          </ResponsiveContainer>

          {/* Custom legend */}
          <ul className="space-y-1.5">
            {chartData.map((entry, i) => {
              const pct = totalSpend > 0 ? ((entry.total / totalSpend) * 100).toFixed(1) : "0";
              return (
                <li key={entry.category} className="flex items-center justify-between gap-2 text-xs">
                  <div className="flex items-center gap-2 min-w-0">
                    <span
                      className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ background: COLORS[i % COLORS.length] }}
                    />
                    <span className="text-slate-300 truncate">{entry.category}</span>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0 text-slate-400">
                    <span>{pct}%</span>
                    <span className="text-slate-500">{fmt(entry.total, currency)}</span>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

function EmptyChart() {
  return (
    <div className="h-52 flex items-center justify-center text-slate-500 text-sm">
      No category data for this period
    </div>
  );
}
