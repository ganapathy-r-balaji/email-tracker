/**
 * StatsBar – row of 3 summary stat tiles for the dashboard header.
 *
 * Shows: Total Orders | Pending Delivery | Delivered
 * Accepts StatsSummary from /api/stats/summary, or null while loading.
 */

import { Package, Truck, CheckCircle } from "lucide-react";
import type { StatsSummary } from "@/lib/api";

interface StatsBarProps {
  stats: StatsSummary | undefined;
  loading: boolean;
}

export function StatsBar({ stats, loading }: StatsBarProps) {
  const tiles = [
    {
      label: "Total Orders",
      value: stats?.total_orders ?? 0,
      icon: <Package className="w-5 h-5 text-blue-400" />,
      color: "text-blue-400",
    },
    {
      label: "Pending Delivery",
      value: stats?.pending_delivery ?? 0,
      icon: <Truck className="w-5 h-5 text-amber-400" />,
      color: "text-amber-400",
    },
    {
      label: "Delivered",
      value: stats?.delivered ?? 0,
      icon: <CheckCircle className="w-5 h-5 text-emerald-400" />,
      color: "text-emerald-400",
    },
  ];

  return (
    <div className="grid grid-cols-3 gap-3 sm:gap-4">
      {tiles.map((tile) => (
        <div
          key={tile.label}
          className="rounded-xl border border-slate-800 bg-slate-900 px-4 py-4 sm:px-6 sm:py-5"
        >
          <div className="flex items-center gap-2 mb-1">
            {tile.icon}
            <span className="text-xs text-slate-400 font-medium hidden sm:block">
              {tile.label}
            </span>
          </div>
          {loading ? (
            <div className="h-7 w-10 bg-slate-800 rounded animate-pulse mt-1" />
          ) : (
            <p className={`text-2xl font-bold ${tile.color}`}>{tile.value}</p>
          )}
          <p className="text-xs text-slate-500 mt-0.5 sm:hidden">{tile.label}</p>
        </div>
      ))}
    </div>
  );
}
