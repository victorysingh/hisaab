"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ArrowDownLeft, ArrowRight, Mic, PartyPopper, RotateCcw, Wallet } from "lucide-react";
import { Avatar } from "@/components/avatar";
import { CountUp } from "@/components/count-up";
import { DaysLateBadge } from "@/components/days-late-badge";
import { LogoMark } from "@/components/logo";
import { RemindButton } from "@/components/remind-button";
import { Sparkle, Ticker } from "@/components/ticker";
import {
  api,
  BUSINESS_NAME,
  num,
  rupees,
  shortDate,
  type Customer,
  type DuesResponse,
  type DuesRow,
  type Forecast,
} from "@/lib/api";

type Data = { dues: DuesResponse; forecast: Forecast; customers: Customer[] };

const ASK_EVENT = "hisaab:ask";
const PROMPTS = ["Will I manage rent next month?", "What if Kabir pays 15 days late?", "Who should I chase today?"];

/** Smallest set of dues likely to be paid soon that covers the shortfall (max 3 people).
 *  Recently late parents (1-2 months owed) come first; long-term non-payers (3+ months) last. */
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

function ask(text: string) {
  window.dispatchEvent(new CustomEvent(ASK_EVENT, { detail: { text } }));
}

export default function HomePage() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [received, setReceived] = useState<string | null>(null);
  const prevDues = useRef<Map<string, { name: string; due: number }> | null>(null);

  useEffect(() => {
    const load = () =>
      // Check open Razorpay links first (works even without a webhook), then load everything.
      api("/payment-links/sync", { method: "POST" })
        .catch(() => null)
        .then(() =>
          Promise.all([
            api<DuesResponse>("/dashboard/dues"),
            api<Forecast>("/forecast?days=60"),
            api<Customer[]>("/customers"),
          ]),
        )
        .then(([dues, forecast, customers]) => {
          // Spot payments that arrived since the last refresh, for the "payment received" banner.
          const now = new Map(dues.rows.map((r) => [r.customer_id, { name: r.customer_name, due: num(r.total_due) }]));
          if (prevDues.current) {
            const paid: string[] = [];
            prevDues.current.forEach((before, id) => {
              const after = now.get(id)?.due ?? 0;
              if (after < before.due) paid.push(`${rupees(before.due - after)} from ${before.name}`);
            });
            if (paid.length) {
              setReceived(`Payment received: ${paid.join(", ")}`);
              setTimeout(() => setReceived(null), 8000);
            }
          }
          prevDues.current = now;
          setData({ dues, forecast, customers });
          setError(null);
        })
        .catch((e: Error) => setError(e.message));
    load();
    // Refresh every 5 seconds so payments (SMS, Razorpay, voice) show up live.
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  if (error && !data) {
    return (
      <main className="w-full space-y-4 p-4">
        <h1 className="font-display text-3xl font-extrabold">Hisaab</h1>
        <p className="brut-card p-4 text-sm">
          Could not load your data: {error}. Is the API running? It can take about a minute to wake up.
        </p>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="w-full">
        <section className="h-72 animate-pulse bg-[var(--hero)]" />
        <div className="space-y-4 p-4">
          <div className="h-24 animate-pulse rounded-2xl bg-black/5" />
          <div className="h-56 animate-pulse rounded-2xl bg-black/5" />
        </div>
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
  const lateHabit = forecast.assumptions.find((a) => a.includes("usually pays"));
  const rentLine = forecast.assumptions.find((a) => a.toLowerCase().startsWith("rent"));

  const tickerItems = [
    `${rupees(dues.totals.total_outstanding)} pending`,
    `${dues.rows.length} parents to follow up`,
    shortfall ? `${rupees(shortfall.amount)} short on ${shortDate(shortfall.date)}` : "Covered for 60 days",
    (rentLine ?? "").replace(/Rs /g, "₹"),
    `${rupees(dues.totals.collected_this_month)} collected this month`,
    (lateHabit ?? "").replace(/Rs /g, "₹"),
    "Say: who should I chase today?",
  ];

  return (
    <main className="w-full pb-4">
      {/* HERO */}
      <section className="relative overflow-hidden bg-[var(--hero)] px-5 pb-12 pt-5 text-white">
        <Sparkle className="right-8 top-16 text-[var(--lime)]" size={18} />
        <Sparkle className="right-24 top-36 text-white" size={10} delay={0.8} />
        <Sparkle className="left-6 bottom-8 text-[var(--saffron)]" size={12} delay={1.4} />
        <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-white/10 float" />

        <header className="relative flex items-center justify-between">
          <div className="flex items-center gap-3">
            <LogoMark className="h-10 w-10 rounded-[10px] border-2 border-[var(--ink)] shadow-[3px_3px_0_var(--ink)]" />
            <div>
              <p className="text-xs font-medium text-white/75">Namaste, Priya 👋</p>
              <p className="font-display text-lg font-bold leading-tight">{BUSINESS_NAME}</p>
            </div>
          </div>
          <span className="chip bg-[var(--paper)] text-[var(--ink)]">{shortDate(forecast.today)}</span>
        </header>

        <p className="relative mt-7 text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--lime)]">
          Action today
        </p>
        {shortfall ? (
          <h1 className="rise relative mt-2 font-display text-[34px] font-extrabold leading-[1.05]">
            You&apos;ll be <span className="hl">{rupees(shortfall.amount)}</span> short on{" "}
            <span className="whitespace-nowrap">{shortDate(shortfall.date)}</span>
          </h1>
        ) : (
          <h1 className="rise relative mt-2 font-display text-[34px] font-extrabold leading-[1.05]">
            You&apos;re <span className="hl">covered</span> for the next 60 days
          </h1>
        )}
        {chase.length > 0 && (
          <p className="rise relative mt-3 text-[15px] text-white/90" style={{ animationDelay: "0.08s" }}>
            Chase {nameList} today: {chase.length > 1 ? "together " : ""}
            {rupees(chaseTotal)}
            {shortfall && chaseTotal >= num(shortfall.amount) ? ", enough to cover it." : " pending."}
          </p>
        )}
        <div className="rise relative mt-5 flex flex-wrap gap-2.5" style={{ animationDelay: "0.16s" }}>
          {chase.map((r) => {
            const c = byId.get(r.customer_id);
            return (
              <RemindButton
                key={r.customer_id}
                customerId={r.customer_id}
                phone={c?.phone}
                guardian={c?.guardian_name}
                student={r.customer_name}
                amount={r.total_due}
                since={r.oldest_due_date}
                daysLate={r.days_late}
                label={`Remind ${r.customer_name.split(" ")[0]}`}
                className="brut-btn bg-[var(--saffron)] hover:bg-[var(--saffron)]"
              />
            );
          })}
          <Link href="/forecast" className="brut-btn bg-white">
            See forecast <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>

      <div className="-mt-4">
        <Ticker items={tickerItems} />
      </div>

      <div className="space-y-5 px-4 pt-7">
        {received && (
          <div className="pop brut-card flex items-center gap-3 bg-[var(--lime)] p-3 text-sm font-bold">
            <PartyPopper className="h-5 w-5 shrink-0" />
            {received}
          </div>
        )}

        {/* STATS */}
        <section className="grid grid-cols-3 gap-3">
          {[
            { label: "Outstanding", value: num(dues.totals.total_outstanding), icon: Wallet, tone: "bg-[var(--coral)]" },
            { label: "Collected this month", value: num(dues.totals.collected_this_month), icon: ArrowDownLeft, tone: "bg-[var(--lime)]" },
            { label: "Recovered late fees", value: num(dues.totals.recovered_this_month), icon: RotateCcw, tone: "bg-[var(--saffron)]" },
          ].map((t, i) => (
            <div key={t.label} className="rise brut-card lift p-3" style={{ animationDelay: `${0.1 + i * 0.07}s` }}>
              <span className={"inline-flex h-8 w-8 items-center justify-center rounded-lg border-2 border-[var(--ink)] " + t.tone}>
                <t.icon className="h-4 w-4 text-[var(--ink)]" />
              </span>
              <p className="mt-2 font-display text-lg font-extrabold leading-tight">
                <CountUp value={t.value} />
              </p>
              <p className="text-[11px] font-medium leading-tight text-black/60">{t.label}</p>
            </div>
          ))}
        </section>

        {/* ASK */}
        <section className="rise brut-card bg-[var(--paper)] p-4" style={{ animationDelay: "0.3s" }}>
          <p className="flex items-center gap-2 font-display text-base font-bold">
            <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-[var(--ink)] text-[var(--lime)]">
              <Mic className="h-4 w-4" />
            </span>
            Just ask Hisaab
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {PROMPTS.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => ask(p)}
                className="rounded-full border-2 border-[var(--ink)] bg-white px-3 py-1 text-xs font-semibold transition-colors hover:bg-[var(--lime)]"
              >
                &ldquo;{p}&rdquo;
              </button>
            ))}
          </div>
        </section>

        {/* WHO OWES */}
        <section className="rise brut-card overflow-hidden" style={{ animationDelay: "0.38s" }}>
          <div className="flex items-center justify-between border-b-2 border-[var(--ink)] bg-[var(--saffron)] px-4 py-3">
            <h2 className="font-display text-lg font-extrabold">Who owes you</h2>
            <Link href="/dues" className="chip bg-white">
              See all →
            </Link>
          </div>
          {dues.rows.length === 0 ? (
            <p className="p-4 text-sm">Nobody owes you anything right now. 🎉</p>
          ) : (
            <ul className="divide-y-2 divide-black/10">
              {dues.rows.slice(0, 5).map((r) => (
                <li key={r.customer_id} className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-[var(--paper)]">
                  <Avatar name={r.customer_name} className="border-2 border-[var(--ink)]" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold">{r.customer_name}</p>
                    <p className="text-xs text-black/55">
                      since {shortDate(r.oldest_due_date)} · {r.invoice_count} month{r.invoice_count > 1 ? "s" : ""}
                    </p>
                  </div>
                  <DaysLateBadge days={r.days_late} />
                  <p className="w-20 text-right font-display font-extrabold">{rupees(r.total_due)}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
