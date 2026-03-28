/**
 * OrderCard – expandable card for a single order.
 *
 * Collapsed view: vendor, status badge, order date, total price, item count, tracking number
 * Expanded view:  full item list with quantities + prices, all shipment details with tracking link
 */

"use client";

import { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Package,
  Truck,
} from "lucide-react";
import type { Order, Shipment } from "@/lib/api";
import { StatusBadge } from "./StatusBadge";

interface OrderCardProps {
  order: Order;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatPrice(price: number | null, currency: string | null): string {
  if (price == null) return "—";
  const code = currency ?? "USD";
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency: code }).format(price);
  } catch {
    return `${code} ${price.toFixed(2)}`;
  }
}

function ShipmentRow({ shipment }: { shipment: Shipment }) {
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-3 space-y-1.5">
      <div className="flex items-center gap-2">
        <Truck className="w-3.5 h-3.5 text-amber-400 shrink-0" />
        <span className="text-xs font-medium text-slate-200">
          {shipment.carrier ?? "Carrier unknown"}
          {shipment.tracking_number && (
            <span className="text-slate-400 font-normal ml-1">
              · {shipment.tracking_number}
            </span>
          )}
        </span>
        {shipment.tracking_url && (
          <a
            href={shipment.tracking_url}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto text-blue-400 hover:text-blue-300 transition-colors"
            onClick={(e) => e.stopPropagation()}
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        )}
      </div>
      <div className="grid grid-cols-3 gap-2 text-xs text-slate-400">
        <div>
          <p className="text-slate-500 text-[10px] uppercase tracking-wide">Shipped</p>
          <p>{formatDate(shipment.shipped_date)}</p>
        </div>
        <div>
          <p className="text-slate-500 text-[10px] uppercase tracking-wide">Est. Delivery</p>
          <p>{formatDate(shipment.estimated_delivery)}</p>
        </div>
        <div>
          <p className="text-slate-500 text-[10px] uppercase tracking-wide">Delivered</p>
          <p className={shipment.actual_delivery ? "text-emerald-400" : ""}>
            {formatDate(shipment.actual_delivery)}
          </p>
        </div>
      </div>
    </div>
  );
}

export function OrderCard({ order }: OrderCardProps) {
  const [expanded, setExpanded] = useState(false);

  const latestShipment = order.latest_shipment;
  const trackingDisplay = latestShipment?.tracking_number ?? null;

  return (
    <div
      className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden
                 hover:border-slate-700 transition-colors duration-150 cursor-pointer"
      onClick={() => setExpanded((prev) => !prev)}
    >
      {/* ── Collapsed header ─────────────────────────────────────────────── */}
      <div className="px-4 py-4 sm:px-5">
        <div className="flex items-start justify-between gap-3">
          {/* Left: vendor + order ID */}
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 rounded-lg bg-slate-800 flex items-center justify-center shrink-0">
              <Package className="w-4 h-4 text-slate-400" />
            </div>
            <div className="min-w-0">
              <p className="font-semibold text-white text-sm truncate">
                {order.vendor ?? "Unknown vendor"}
              </p>
              {order.vendor_order_id && (
                <p className="text-slate-500 text-xs truncate">#{order.vendor_order_id}</p>
              )}
            </div>
          </div>

          {/* Right: status badge + chevron */}
          <div className="flex items-center gap-2 shrink-0">
            <StatusBadge status={order.status} />
            {expanded ? (
              <ChevronUp className="w-4 h-4 text-slate-500" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-500" />
            )}
          </div>
        </div>

        {/* Meta row */}
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
          <span>{formatDate(order.order_date)}</span>
          {order.total_price != null && (
            <span className="font-medium text-slate-300">
              {formatPrice(order.total_price, order.currency)}
            </span>
          )}
          <span>
            {order.item_count} {order.item_count === 1 ? "item" : "items"}
          </span>
          {trackingDisplay && !expanded && (
            <span className="text-slate-500">
              Tracking: {trackingDisplay}
            </span>
          )}
        </div>
      </div>

      {/* ── Expanded detail ───────────────────────────────────────────────── */}
      {expanded && (
        <div
          className="border-t border-slate-800 px-4 py-4 sm:px-5 space-y-4"
          onClick={(e) => e.stopPropagation()} // don't collapse when clicking inside
        >
          {/* Items */}
          {order.items.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
                Items
              </h4>
              <div className="space-y-1.5">
                {order.items.map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center justify-between gap-3 text-sm"
                  >
                    <span className="text-slate-200 min-w-0 truncate">
                      {item.quantity > 1 && (
                        <span className="text-slate-400 mr-1.5">×{item.quantity}</span>
                      )}
                      {item.name}
                    </span>
                    {item.unit_price != null && (
                      <span className="text-slate-400 shrink-0 text-xs">
                        {formatPrice(item.unit_price, order.currency)}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Shipments */}
          {latestShipment && (
            <div>
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
                Shipment
              </h4>
              <ShipmentRow shipment={latestShipment} />
            </div>
          )}

          {/* No shipment info */}
          {!latestShipment && (
            <p className="text-xs text-slate-500">No shipment information yet.</p>
          )}
        </div>
      )}
    </div>
  );
}
