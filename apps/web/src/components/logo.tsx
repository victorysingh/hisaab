import { cn } from "@/lib/utils";

/** Hisaab mark: a teal tile with a rupee sign and a small sound wave (voice-first). */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden className={cn("h-8 w-8", className)}>
      <rect width="32" height="32" rx="8" fill="#0f766e" />
      <path
        d="M10 9h12M10 14h12M10 9c5 0 7 2 7 5s-3 5-7 5l8 6"
        fill="none"
        stroke="white"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="25" cy="24" r="1.4" fill="#5eead4" />
      <circle cx="25" cy="19.5" r="1" fill="#5eead4" />
    </svg>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <LogoMark />
      <span className="text-lg font-semibold tracking-tight">Hisaab</span>
    </span>
  );
}
