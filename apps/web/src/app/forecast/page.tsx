"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ForecastChart } from "@/components/forecast-chart";
import {
  api,
  nextPeriod,
  num,
  rupees,
  shortDate,
  type Customer,
  type Forecast,
  type WhatIfChange,
  WHAT_IF_EVENT,
  WHAT_IF_STORAGE_KEY,
} from "@/lib/api";

const HORIZONS = [30, 60, 90] as const;

function describe(change: WhatIfChange, names: Map<string, string>): string {
  switch (change.type) {
    case "delay":
      return `${names.get(change.customer_id) ?? "Student"} pays ${change.days} days late`;
    case "drop":
      return `${change.customer_ids.map((id) => names.get(id) ?? "Student").join(", ")} leave${
        change.customer_ids.length > 1 ? "" : "s"
      } from ${change.from_period}`;
    case "new_bill":
      return `${change.name} ${rupees(change.amount)} on ${shortDate(change.date)}`;
    case "new_customer":
      return `New student at ${rupees(change.monthly_fee)}/mo from ${change.start_period}`;
  }
}

function Headline({ f, label }: { f: Forecast; label?: string }) {
  const lowest = f.days.reduce((min, d) => (num(d.likely) < num(min.likely) ? d : min), f.days[0]);
  return (
    <div>
      {label && <p className="text-xs font-medium uppercase tracking-wide text-amber-700">{label}</p>}
      {f.shortfall ? (
        <p className="text-lg font-semibold text-red-700">
          You&apos;ll be {rupees(f.shortfall.amount)} short on {shortDate(f.shortfall.date)}
        </p>
      ) : (
        <p className="text-lg font-semibold text-emerald-700">You&apos;re covered for the next {f.days_ahead} days</p>
      )}
      <p className="text-sm text-muted-foreground">
        Lowest point: {rupees(lowest.likely)} on {shortDate(lowest.date)} · today {rupees(f.start_balance)}
      </p>
    </div>
  );
}

export default function ForecastPage() {
  const [days, setDays] = useState<(typeof HORIZONS)[number]>(60);
  const [base, setBase] = useState<Forecast | null>(null);
  const [scenario, setScenario] = useState<Forecast | null>(null);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [changes, setChanges] = useState<WhatIfChange[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showAssumptions, setShowAssumptions] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  // what-if form state
  const [delayCustomer, setDelayCustomer] = useState("");
  const [delayDays, setDelayDays] = useState(15);
  const [leaveCustomer, setLeaveCustomer] = useState("");
  const [billName, setBillName] = useState("");
  const [billAmount, setBillAmount] = useState("");
  const [billDate, setBillDate] = useState("");

  const names = useMemo(() => new Map(customers.map((c) => [c.id, c.name])), [customers]);
  const active = useMemo(() => customers.filter((c) => c.status === "active"), [customers]);

  // Load customers once, and pick up any what-if left by the voice agent.
  useEffect(() => {
    api<Customer[]>("/customers").then(setCustomers).catch(() => setCustomers([]));
    try {
      const pending = sessionStorage.getItem(WHAT_IF_STORAGE_KEY);
      if (pending) {
        setChanges(JSON.parse(pending) as WhatIfChange[]);
        sessionStorage.removeItem(WHAT_IF_STORAGE_KEY);
      }
    } catch {
      // storage unavailable
    }
    const onEvent = (e: Event) => setChanges((e as CustomEvent<{ changes: WhatIfChange[] }>).detail.changes);
    const onData = () => setRefreshKey((k) => k + 1);
    window.addEventListener(WHAT_IF_EVENT, onEvent);
    window.addEventListener("hisaab:data-changed", onData);
    return () => {
      window.removeEventListener(WHAT_IF_EVENT, onEvent);
      window.removeEventListener("hisaab:data-changed", onData);
    };
  }, []);

  // Baseline forecast whenever the horizon changes.
  useEffect(() => {
    setBase(null);
    api<Forecast>(`/forecast?days=${days}`)
      .then((f) => {
        setBase(f);
        setError(null);
      })
      .catch((e: Error) => setError(e.message));
  }, [days, refreshKey]);

  // What-if scenario, debounced.
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    if (changes.length === 0) {
      setScenario(null);
      return;
    }
    timer.current = setTimeout(() => {
      api<Forecast>("/forecast/what-if", { method: "POST", body: JSON.stringify({ days, changes }) })
        .then(setScenario)
        .catch((e: Error) => setError(e.message));
    }, 300);
  }, [changes, days]);

  // Keep the delay slider live: replace that student's delay change as the slider moves.
  function applyDelay(customerId: string, d: number) {
    setChanges((prev) => [
      ...prev.filter((c) => !(c.type === "delay" && c.customer_id === customerId)),
      ...(customerId && d > 0 ? [{ type: "delay" as const, customer_id: customerId, days: d }] : []),
    ]);
  }

  function addLeave() {
    if (!leaveCustomer || !base) return;
    setChanges((prev) => [
      ...prev,
      { type: "drop", customer_ids: [leaveCustomer], from_period: nextPeriod(base.today) },
    ]);
    setLeaveCustomer("");
  }

  function addBill() {
    if (!billName || !Number(billAmount) || !billDate) return;
    setChanges((prev) => [
      ...prev,
      { type: "new_bill", name: billName, amount: Number(billAmount), date: billDate, recurrence: "once" },
    ]);
    setBillName("");
    setBillAmount("");
    setBillDate("");
  }

  const shown = scenario ?? base;

  return (
    <main className="mx-auto w-full max-w-md space-y-4 p-4">
      <header className="flex items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Forecast</h1>
          <p className="text-sm text-muted-foreground">Your cash over the next {days} days.</p>
        </div>
        <div className="flex rounded-lg border p-0.5">
          {HORIZONS.map((h) => (
            <button
              key={h}
              type="button"
              onClick={() => setDays(h)}
              className={
                "rounded-md px-2.5 py-1 text-sm " + (days === h ? "bg-foreground text-background" : "text-muted-foreground")
              }
            >
              {h}d
            </button>
          ))}
        </div>
      </header>

      {error && (
        <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          Could not load the forecast: {error}
        </p>
      )}

      {!base && !error && <div className="h-80 animate-pulse rounded-xl bg-muted" />}

      {base && shown && (
        <>
          <section className="space-y-3 rounded-xl border p-4">
            {scenario ? (
              <>
                <Headline f={scenario} label="What-if" />
                <p className="text-xs text-muted-foreground">
                  Without changes:{" "}
                  {base.shortfall
                    ? `${rupees(base.shortfall.amount)} short on ${shortDate(base.shortfall.date)}`
                    : "no shortfall"}
                </p>
              </>
            ) : (
              <Headline f={base} />
            )}
            <ForecastChart base={base} scenario={scenario} />
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <span className="inline-block h-0.5 w-4 bg-[#0f766e]" /> Likely
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block h-2.5 w-4 rounded-sm bg-[#0f766e]/15" /> Best to worst
              </span>
              {scenario && (
                <span className="flex items-center gap-1">
                  <span className="inline-block h-0.5 w-4 border-t-2 border-dashed border-[#d97706]" /> What-if
                </span>
              )}
              <span className="flex items-center gap-1">
                <span className="inline-block h-0.5 w-4 border-t border-dashed border-[#dc2626]" /> Safety line
              </span>
            </div>
          </section>

          {shown.causes.length > 0 && (
            <section className="rounded-xl border">
              <h2 className="border-b px-4 py-2 text-sm font-semibold">Why</h2>
              <ul className="divide-y">
                {shown.causes.map((c, i) => (
                  <li key={i} className="flex items-center justify-between gap-3 px-4 py-2 text-sm">
                    <span className="min-w-0 truncate">
                      {c.label}
                      <span className="ml-2 text-xs text-muted-foreground">
                        {c.type === "bill" ? `due ${shortDate(c.date)}` : `unpaid since ${shortDate(c.date)}`}
                      </span>
                    </span>
                    <span className="font-medium">{rupees(c.amount)}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* What-if panel */}
          <section className="space-y-4 rounded-xl border p-4">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold">What if…</h2>
              {changes.length > 0 && (
                <Button type="button" size="sm" variant="ghost" onClick={() => setChanges([])}>
                  Reset
                </Button>
              )}
            </div>

            {changes.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {changes.map((c, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-3 py-1 text-xs text-amber-900"
                  >
                    {describe(c, names)}
                    <button
                      type="button"
                      aria-label="Remove"
                      onClick={() => setChanges((prev) => prev.filter((_, j) => j !== i))}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}

            <div className="space-y-2">
              <label className="text-sm font-medium">A student pays late</label>
              <select
                value={delayCustomer}
                onChange={(e) => {
                  setDelayCustomer(e.target.value);
                  applyDelay(e.target.value, delayDays);
                }}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              >
                <option value="">Choose a student</option>
                {active.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min={0}
                  max={30}
                  value={delayDays}
                  disabled={!delayCustomer}
                  onChange={(e) => {
                    const d = Number(e.target.value);
                    setDelayDays(d);
                    applyDelay(delayCustomer, d);
                  }}
                  className="flex-1 accent-[#d97706]"
                />
                <span className="w-16 text-right text-sm">{delayDays} days</span>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">A student leaves next month</label>
              <div className="flex gap-2">
                <select
                  value={leaveCustomer}
                  onChange={(e) => setLeaveCustomer(e.target.value)}
                  className="min-w-0 flex-1 rounded-md border bg-background px-3 py-2 text-sm"
                >
                  <option value="">Choose a student</option>
                  {active.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
                <Button type="button" variant="outline" onClick={addLeave} disabled={!leaveCustomer}>
                  Add
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">A one-off expense</label>
              <Input placeholder="e.g. New projector" value={billName} onChange={(e) => setBillName(e.target.value)} />
              <div className="flex gap-2">
                <Input
                  placeholder="Amount"
                  inputMode="numeric"
                  value={billAmount}
                  onChange={(e) => setBillAmount(e.target.value)}
                  className="flex-1"
                />
                <Input type="date" value={billDate} onChange={(e) => setBillDate(e.target.value)} className="flex-1" />
              </div>
              <Button
                type="button"
                variant="outline"
                className="w-full"
                onClick={addBill}
                disabled={!billName || !Number(billAmount) || !billDate}
              >
                Add expense
              </Button>
            </div>
          </section>

          <section className="rounded-xl border">
            <button
              type="button"
              onClick={() => setShowAssumptions((s) => !s)}
              className="flex w-full items-center justify-between px-4 py-3 text-sm font-semibold"
            >
              How this is worked out
              <span className="text-muted-foreground">{showAssumptions ? "−" : "+"}</span>
            </button>
            {showAssumptions && (
              <ul className="space-y-1 border-t px-4 py-3 text-sm text-muted-foreground">
                {shown.assumptions.map((a, i) => (
                  <li key={i}>• {a}</li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </main>
  );
}
