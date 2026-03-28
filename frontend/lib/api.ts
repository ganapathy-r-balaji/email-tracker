/**
 * lib/api.ts – Typed Axios client for the FastAPI backend.
 *
 * withCredentials: true  → sends the session cookie with every request
 * (mirrors allow_credentials=True on the backend CORS config)
 */

import axios, { AxiosError } from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const apiClient = axios.create({
  baseURL: API_URL,
  withCredentials: true, // critical: send session cookie cross-origin
});

// ─── Types ────────────────────────────────────────────────────────────────────

export interface CurrentUser {
  id: number;
  email: string;
  last_sync_at: string | null;
  created_at: string;
}

export interface Item {
  id: number;
  name: string;
  quantity: number;
  unit_price: number | null;
  category: string | null;
}

export interface Shipment {
  id: number;
  tracking_number: string | null;
  carrier: string | null;
  shipped_date: string | null;
  estimated_delivery: string | null;
  actual_delivery: string | null;
  tracking_url: string | null;
}

export interface Order {
  id: number;
  vendor_order_id: string | null;
  vendor: string | null;
  order_date: string | null;
  total_price: number | null;
  currency: string | null;
  status: "ordered" | "shipped" | "delivered" | "unknown";
  items: Item[];
  item_count: number;
  shipments: Shipment[] | null;
  latest_shipment: Shipment | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedOrders {
  orders: Order[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface StatsSummary {
  total_orders: number;
  pending_delivery: number;
  delivered: number;
  last_sync_at: string | null;
  top_vendors: { name: string; count: number }[];
}

// ─── API functions ────────────────────────────────────────────────────────────

export const authApi = {
  /** Fetch the current authenticated user. Throws AxiosError 401 if not logged in. */
  me: () => apiClient.get<CurrentUser>("/api/me").then((r) => r.data),

  /** Redirect to logout endpoint (clears session cookie server-side). */
  logout: () => {
    window.location.href = `${API_URL}/auth/logout`;
  },
};

export const ordersApi = {
  list: (page = 1, perPage = 20, status?: string, vendor?: string) => {
    const params: Record<string, string | number> = { page, per_page: perPage };
    if (status) params.status = status;
    if (vendor) params.vendor = vendor;
    return apiClient
      .get<PaginatedOrders>("/api/orders", { params })
      .then((r) => r.data);
  },

  detail: (id: number) =>
    apiClient.get<Order>(`/api/orders/${id}`).then((r) => r.data),

  stats: () =>
    apiClient.get<StatsSummary>("/api/stats/summary").then((r) => r.data),
};

export const syncApi = {
  trigger: () =>
    apiClient.post<{ status: string; message: string }>("/api/sync").then((r) => r.data),

  status: () =>
    apiClient.get<{ last_sync_at: string | null }>("/api/sync/status").then((r) => r.data),
};

/** Helper: check if an Axios error is a 401 Unauthorized. */
export function is401(err: unknown): boolean {
  return axios.isAxiosError(err) && (err as AxiosError).response?.status === 401;
}
