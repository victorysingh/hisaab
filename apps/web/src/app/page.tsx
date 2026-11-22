"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, MessageCircle } from "lucide-react";
import { DaysLateBadge } from "@/components/days-late-badge";
import {
  api,
  num,
  reminderText,
  rupees,
  shortDate,
  whatsappUrl,
  type Customer,
  type DuesResponse,
  type DuesRow,
  type Forecast,
} from "@/lib/api";

type Data = { dues: DuesResponse; forecast: Forecast; customers: Customer[] };

/** Smallest set of dues likely to be paid soon that covers the shortfall (max 3 people).
 *  Recently late parents (1-2 months owed) come first; long-term non-payers (3+ months) last,
 *  because chasing them rarely brings money in before the shortfall date. */
function pickChase(rows: DuesRow[], target: number): DuesRow[] {
  const chronic = (r: DuesRow) => (r.invoice_count >= 3 ? 1 : 0);
  const sorted = [...rows].sort(
    (a, b) => chronic(a) - chronic(b) || num(b.total_due) - num(a.total_due) || b.days_late - a.days_late,
  );
  const picked: DuesRow[] = [];
  let sum = 0;
  for (const r of sorted) {
    if (picked.length >= 3 || (target > 0 && sum >= target)) break;
    picked.push(r);
    sum += num(r.total_due);
  }
  return picked.length ? picked : sorted.slice(0, 2);
}

export default function HomePage() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = () =>
      Promise.all([
        api<DuesResponse>("/dashboard/dues"),
        api<Forecast>("/forecast?days=60"),
        api<Customer[]>("/customers"),
      ])
        .then(([dues, forecast, customers]) => {
          setData({ dues, forecast, customers });
          setError(null);
        })
        .catch((e: Error) => setError(e.message));
    load();
    // Refresh every 5 seconds so a payment from the SMS simulator shows up live.
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  if (error) {
    return (
      <main className="mx-auto w-full max-w-md p-4">
        <h1 className="text-2xl font-semibold">Hisaab</h1>
        <p className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          Could not load your data: {error}. Is the API running?
        </p>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="mx-auto w-full max-w-md space-y-3 p-4">
        <h1 className="text-2xl font-semibold">Hisaab</h1>
        <div className="h-28 animate-pulse rounded-xl bg-muted" />
        <div className="h-20 animate-pulse rounded-xl bg-muted" />
        <div className="h-40 animate-pulse rounded-xl bg-muted" />
      </main>
    );
  }

  const { dues, forecast, customers } = data;
  const byId = new Map(customers.map((c) => [c.id, c]));
  const shortfall = forecast.shortfall;
  const chase = pickChase(dues.rows, shortfall ? num(shortfall.amount) : 0);
  const chaseTotal = chase.reduce((s, r) => s + num(r.total_due), 0);
  const names = chase.map((r) => r.customer_name.split(" ")[0]);
  const nameList = names.length > 1 ? `${names.slice(0, -1).join(", ")} and ${names.at(-1)}` : names[0];

  return (
    <main className="mx-auto w-full max-w-md space-y-4 p-4">
      <header>
        <p className="text-sm text-muted-foreground">Namaste 👋</p>
        <h1 className="text-2xl font-semibold">Hisaab</h1>
      </header>

      {/* Action today */}
      <section
        className={
          "rounded-xl border p-4 " + (shortfall ? "border-red-200 bg-red-50" : "border-emerald-200 bg-emerald-50")
        }
      >
        <div className="flex items-start gap-3">
          {shortfall ? (
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-600" />
          ) : (
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
          )}
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Action today</p>
            {shortfall ? (
              <p className="mt-1 text-lg font-semibold text-red-700">
                You&apos;ll be {rupees(shortfall.amount)} short on {shortDate(shortfall.date)}
              </p>
            ) : (
              <p className="mt-1 text-lg font-semibold text-emerald-700">You&apos;re covered for the next 60 days</p>
            )}
            {chase.length > 0 && (
              <p className="mt-1 text-sm">
                Chase {nameList} today: {chase.length > 1 ? "together " : ""}
                {rupees(chaseTotal)}
                {shortfall && chaseTotal >= num(shortfall.amount) ? ", enough to cover it." : " pending."}
              </p>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              {chase.map((r) => {
                const c = byId.get(r.customer_id);
                return (
                  <a
                    key={r.customer_id}
                    href={whatsappUrl(
                      c?.phone,
                      reminderText({
                        guardian: c?.guardian_name,
                        student: r.customer_name,
                        amount: r.total_due,
                        since: r.oldest_due_date,
                      }),
                    )}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 rounded-full border bg-background px-3 py-1 text-sm hover:bg-muted"
                  >
                    <MessageCircle className="h-4 w-4 text-emerald-600" />
                    Remind {r.customer_name.split(" ")[0]}
                  </a>
                );
              })}
              <Link
                href="/forecast"
                className="inline-flex items-center rounded-full border bg-background px-3 py-1 text-sm hover:bg-muted"
              >
                See forecast →
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Stat tiles */}
      <section className="grid grid-cols-3 gap-2">
        {[
          { label: "Outstanding", value: dues.totals.total_outstanding },
          { label: "Collected this month", value: dues.totals.collected_this_month },
          { label: "Recovered this month", value: dues.totals.recovered_this_month },
        ].map((t) => (
          <div key={t.label} className="rounded-xl border p-3">
            <p className="text-[11px] leading-tight text-muted-foreground">{t.label}</p>
            <p className="mt-1 text-base font-semibold">{rupees(t.value)}</p>
          </div>
        ))}
      </section>

      {/* Top dues */}
      <section className="rounded-xl border">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="font-semibold">Who owes you</h2>
          <Link href="/dues" className="text-sm text-muted-foreground hover:underline">
            See all
          </Link>
        </div>
        {dues.rows.length === 0 ? (
          <p className="p-4 text-sm text-muted-foreground">Nobody owes you anything right now.</p>
        ) : (
          <ul className="divide-y">
            {dues.rows.slice(0, 5).map((r) => (
              <li key={r.customer_id} className="flex items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{r.customer_name}</p>
                  <p className="text-xs text-muted-foreground">
                    since {shortDate(r.oldest_due_date)} · {r.invoice_count} month{r.invoice_count > 1 ? "s" : ""}
                  </p>
                </div>
                <DaysLateBadge days={r.days_late} />
                <p className="w-20 text-right font-semibold">{rupees(r.total_due)}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
