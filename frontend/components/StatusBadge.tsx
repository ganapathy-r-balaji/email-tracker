/**
 * StatusBadge – color-coded pill for order status.
 *
 * ordered   → blue
 * shipped   → amber
 * delivered → emerald
 * unknown   → slate
 */

import type { Order } from "@/lib/api";

type Status = Order["status"];

const config: Record<Status, { label: string; classes: string }> = {
  ordered: {
    label: "Ordered",
    classes: "bg-blue-500/15 text-blue-400 ring-blue-500/30",
  },
  shipped: {
    label: "Shipped",
    classes: "bg-amber-500/15 text-amber-400 ring-amber-500/30",
  },
  delivered: {
    label: "Delivered",
    classes: "bg-emerald-500/15 text-emerald-400 ring-emerald-500/30",
  },
  unknown: {
    label: "Unknown",
    classes: "bg-slate-500/15 text-slate-400 ring-slate-500/30",
  },
};

export function StatusBadge({ status }: { status: Status }) {
  const { label, classes } = config[status] ?? config.unknown;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${classes}`}
    >
      {label}
    </span>
  );
}
