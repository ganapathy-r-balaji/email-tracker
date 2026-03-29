"use client";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { ChartSkeleton } from "./SpendingSkeletons";
import type { WeekOfYearEntry } from "@/lib/api";

interface Props {
  data: WeekOfYearEntry[];
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

export function SpendingWeekOfYearChart({ data, loading, currency }: Props) {
  const hasData = data.some((d) => d.total > 0);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4 space-y-3">
      <h3 className="text-sm font-medium text-slate-300">Spending by Week of Year</h3>
      <p className="text-xs text-slate-500">Fine-grained weekly spending pattern</p>
      {loading ? (
        <ChartSkeleton height="h-64" />
      ) : !hasData ? (
        <EmptyChart />
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: "#94a3b8", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              interval={data.length > 26 ? 3 : 1}
            />
            <YAxis
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => fmt(v, currency)}
              width={70}
            />
            <Tooltip
              contentStyle={{
                background: "#0f172a",
                border: "1px solid #1e293b",
                borderRadius: 8,
                color: "#e2e8f0",
              }}
              formatter={(value) => [fmt(Number(value), currency), "Spent"]}
              labelStyle={{ color: "#94a3b8", marginBottom: 4 }}
              cursor={{ fill: "#1e293b" }}
            />
            <Bar dataKey="total" fill="#34d399" radius={[4, 4, 0, 0]} maxBarSize={24} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

function EmptyChart() {
  return (
    <div className="h-64 flex items-center justify-center text-slate-500 text-sm">
      No spending data for this period
    </div>
  );
}
