"use client";

export function ChartSkeleton({ height = "h-52" }: { height?: string }) {
  return (
    <div className={`${height} w-full rounded-xl bg-slate-800 animate-pulse`} />
  );
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2 animate-pulse">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-10 rounded-lg bg-slate-800" />
      ))}
    </div>
  );
}
