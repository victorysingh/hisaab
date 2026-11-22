import { cn } from "@/lib/utils";

/** Green 0-5 days, amber 6-15, red over 15. */
export function DaysLateBadge({ days }: { days: number }) {
  const tone =
    days <= 5
      ? "bg-emerald-100 text-emerald-800"
      : days <= 15
        ? "bg-amber-100 text-amber-800"
        : "bg-red-100 text-red-800";
  return (
    <span className={cn("inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-medium", tone)}>
      {days <= 0 ? "due" : `${days}d late`}
    </span>
  );
}
