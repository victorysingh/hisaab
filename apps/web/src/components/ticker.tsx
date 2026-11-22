/** Slanted, endlessly scrolling strip of live facts. */
export function Ticker({ items }: { items: string[] }) {
  const row = items.filter(Boolean);
  if (!row.length) return null;
  return (
    <div className="ticker relative z-10" aria-label={row.join(". ")}>
      <div className="ticker-track" aria-hidden>
        {[...row, ...row, ...row, ...row].map((t, i) => (
          <span key={i} className="ticker-item">
            {t} <span className="mx-2">✦</span>
          </span>
        ))}
      </div>
    </div>
  );
}

/** Four-point sparkle used as decoration on the hero. */
export function Sparkle({ className, delay = 0, size = 14 }: { className?: string; delay?: number; size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      aria-hidden
      className={"twinkle absolute " + (className ?? "")}
      style={{ animationDelay: `${delay}s` }}
    >
      <path d="M12 0c.6 6.4 5.6 11.4 12 12-6.4.6-11.4 5.6-12 12-.6-6.4-5.6-11.4-12-12 6.4-.6 11.4-5.6 12-12z" fill="currentColor" />
    </svg>
  );
}
