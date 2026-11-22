import { cn } from "@/lib/utils";

/** Green 0-5 days, amber 6-15, red over 15. */
export function DaysLateBadge({ days }: { days: number }) {
  const tone = days <= 5 ? "bg-[var(--lime)]" : days <= 15 ? "bg-[var(--saffron)]" : "bg-[var(--coral)] text-white";
  return <span className={cn("chip", tone)}>{days <= 0 ? "due" : `${days}d late`}</span>;
}
