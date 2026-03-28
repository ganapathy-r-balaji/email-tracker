/**
 * Toast – lightweight notification component.
 *
 * Usage in a page:
 *   const [toast, setToast] = useState<ToastState | null>(null);
 *   <Toast toast={toast} onDismiss={() => setToast(null)} />
 *
 * Auto-dismisses after `duration` ms (default 5000).
 */

"use client";

import { useEffect } from "react";
import { CheckCircle, XCircle, X } from "lucide-react";

export type ToastVariant = "success" | "error";

export interface ToastState {
  message: string;
  variant: ToastVariant;
}

interface ToastProps {
  toast: ToastState | null;
  onDismiss: () => void;
  duration?: number;
}

const variantConfig: Record<ToastVariant, { icon: React.ReactNode; classes: string }> = {
  success: {
    icon: <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />,
    classes: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  },
  error: {
    icon: <XCircle className="w-4 h-4 text-red-400 shrink-0" />,
    classes: "border-red-500/30 bg-red-500/10 text-red-300",
  },
};

export function Toast({ toast, onDismiss, duration = 5000 }: ToastProps) {
  // Auto-dismiss
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(onDismiss, duration);
    return () => clearTimeout(timer);
  }, [toast, onDismiss, duration]);

  if (!toast) return null;

  const { icon, classes } = variantConfig[toast.variant];

  return (
    <div
      className={`fixed bottom-5 right-5 z-50 flex items-center gap-3
                  rounded-xl border px-4 py-3 shadow-lg text-sm max-w-sm
                  animate-in slide-in-from-bottom-2 fade-in duration-200
                  ${classes}`}
    >
      {icon}
      <span className="flex-1">{toast.message}</span>
      <button
        onClick={onDismiss}
        className="ml-1 opacity-60 hover:opacity-100 transition-opacity"
        aria-label="Dismiss"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
