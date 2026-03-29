"use client";

/**
 * DateRangePicker.tsx
 *
 * A start/end date range selector using react-day-picker.
 * The popover is built with a simple absolute-positioned div (no Radix dep).
 * Clicking outside or pressing Escape closes it.
 */

import { useEffect, useRef, useState } from "react";
import { DayPicker, DateRange } from "react-day-picker";
import { CalendarIcon, ChevronDown } from "lucide-react";
import "react-day-picker/dist/style.css";

interface Props {
  startDate: string; // ISO "YYYY-MM-DD"
  endDate: string;
  onChange: (start: string, end: string) => void;
}

function toDate(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function toIso(date: Date): string {
  return date.toISOString().split("T")[0];
}

const PRESETS = [
  { label: "Last 30 days", days: 30 },
  { label: "Last 90 days", days: 90 },
  { label: "Last 6 months", days: 180 },
  { label: "Last 12 months", days: 365 },
  { label: "This year", days: -1 },
] as const;

export function DateRangePicker({ startDate, endDate, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const [range, setRange] = useState<DateRange>({
    from: toDate(startDate),
    to: toDate(endDate),
  });

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, []);

  function applyRange(r: DateRange | undefined) {
    if (!r) return;
    setRange(r);
    if (r.from && r.to) {
      onChange(toIso(r.from), toIso(r.to));
      setOpen(false);
    }
  }

  function applyPreset(days: number) {
    const end = new Date();
    let start: Date;
    if (days === -1) {
      start = new Date(end.getFullYear(), 0, 1); // Jan 1 of current year
    } else {
      start = new Date(end.getTime() - days * 24 * 60 * 60 * 1000);
    }
    const newRange = { from: start, to: end };
    setRange(newRange);
    onChange(toIso(start), toIso(end));
    setOpen(false);
  }

  const displayStart = range.from
    ? range.from.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
    : "Start";
  const displayEnd = range.to
    ? range.to.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
    : "End";

  return (
    <div ref={ref} className="relative">
      {/* Trigger button */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 px-3 py-2 rounded-lg
                   bg-slate-900 border border-slate-700 text-sm text-slate-200
                   hover:border-slate-500 transition-colors"
      >
        <CalendarIcon className="w-4 h-4 text-slate-400" />
        <span>{displayStart}</span>
        <span className="text-slate-500">→</span>
        <span>{displayEnd}</span>
        <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
      </button>

      {/* Dropdown */}
      {open && (
        <div
          className="absolute left-0 top-full mt-2 z-50 rounded-xl border border-slate-700
                     bg-slate-900 shadow-2xl p-4 flex flex-col sm:flex-row gap-4"
          style={{ minWidth: 320 }}
        >
          {/* Presets */}
          <div className="flex flex-col gap-1 sm:w-36">
            <p className="text-xs text-slate-500 font-medium mb-1 px-1">Quick select</p>
            {PRESETS.map((p) => (
              <button
                key={p.label}
                onClick={() => applyPreset(p.days)}
                className="text-left px-2 py-1.5 rounded-lg text-sm text-slate-300
                           hover:bg-slate-800 hover:text-white transition-colors"
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Calendar */}
          <div className="rdp-dark">
            <DayPicker
              mode="range"
              selected={range}
              onSelect={applyRange}
              numberOfMonths={1}
              toDate={new Date()}
              classNames={{
                day_selected: "!bg-blue-600 !text-white",
                day_range_middle: "!bg-blue-900/40 !text-blue-200",
                day_range_start: "!bg-blue-600 !text-white !rounded-l-full",
                day_range_end: "!bg-blue-600 !text-white !rounded-r-full",
                day_today: "!font-bold !text-blue-400",
                caption: "!text-slate-200",
                nav_button: "!text-slate-400 hover:!text-white",
                head_cell: "!text-slate-500 !text-xs",
                day: "!text-slate-300 hover:!bg-slate-700 !rounded-lg",
                table: "!border-collapse",
              }}
              styles={{
                caption: { color: "#e2e8f0" },
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
