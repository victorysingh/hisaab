"use client";

import { useCallback, useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, rupees, shortDate, type Money } from "@/lib/api";

type Bill = {
  id: string;
  name: string;
  amount: Money;
  due_day: number;
  recurrence: "monthly" | "once";
  next_due_date: string | null;
};
type SettingsView = {
  business: { id: string; name: string; opening_balance: Money; safety_buffer: Money };
  bills: Bill[];
};

function ordinal(n: number): string {
  const s = n % 100 >= 11 && n % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th";
  return `${n}${s}`;
}

export default function SettingsPage() {
  const [view, setView] = useState<SettingsView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [cash, setCash] = useState("");
  const [buffer, setBuffer] = useState("");
  const [billName, setBillName] = useState("");
  const [billAmount, setBillAmount] = useState("");
  const [billDay, setBillDay] = useState("1");
  const [billOnce, setBillOnce] = useState(false);
  const [billDate, setBillDate] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api<SettingsView>("/settings")
      .then((v) => {
        setView(v);
        setCash(String(Math.round(Number(v.business.opening_balance || 0))));
        setBuffer(String(Math.round(Number(v.business.safety_buffer || 0))));
      })
      .catch((e: Error) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  async function run(fn: () => Promise<unknown>, message: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await fn();
      setNotice(message);
      window.dispatchEvent(new Event("hisaab:data-changed"));
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const monthlyTotal = (view?.bills || [])
    .filter((b) => b.recurrence === "monthly")
    .reduce((s, b) => s + Number(b.amount), 0);

  return (
    <main className="mx-auto w-full max-w-md space-y-4 p-4">
      <header>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-sm text-muted-foreground">{view?.business.name ?? "Your business"}</p>
      </header>

      {error && <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      {notice && (
        <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>
      )}
      {!view && !error && <div className="h-64 animate-pulse rounded-xl bg-muted" />}

      {view && (
        <>
          <section className="space-y-3 rounded-xl border p-4">
            <h2 className="font-semibold">Cash</h2>
            <label className="block space-y-1 text-sm">
              <span className="text-muted-foreground">Cash in hand today (₹)</span>
              <Input inputMode="numeric" value={cash} onChange={(e) => setCash(e.target.value)} />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-muted-foreground">Warn me if cash may drop below (₹)</span>
              <Input inputMode="numeric" value={buffer} onChange={(e) => setBuffer(e.target.value)} />
            </label>
            <Button
              type="button"
              className="w-full"
              disabled={busy}
              onClick={() =>
                run(
                  () =>
                    api("/settings", {
                      method: "PATCH",
                      body: JSON.stringify({ opening_balance: Number(cash) || 0, safety_buffer: Number(buffer) || 0 }),
                    }),
                  "Saved. Your forecast is updated.",
                )
              }
            >
              Save
            </Button>
          </section>

          <section className="rounded-xl border">
            <div className="flex items-center justify-between border-b px-4 py-3">
              <h2 className="font-semibold">Bills</h2>
              <span className="text-sm text-muted-foreground">{rupees(monthlyTotal)}/month</span>
            </div>
            {view.bills.length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground">No bills yet. Add rent, salary and utilities below.</p>
            ) : (
              <ul className="divide-y">
                {view.bills.map((b) => (
                  <li key={b.id} className="flex items-center gap-3 px-4 py-3">
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium">{b.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {b.recurrence === "monthly"
                          ? `Every month on the ${ordinal(b.due_day)}`
                          : `Once, on ${b.next_due_date ? shortDate(b.next_due_date) : "-"}`}
                      </p>
                    </div>
                    <p className="font-semibold">{rupees(b.amount)}</p>
                    <button
                      type="button"
                      aria-label={`Remove ${b.name}`}
                      disabled={busy}
                      onClick={() => run(() => api(`/settings/bills/${b.id}`, { method: "DELETE" }), `Removed ${b.name}.`)}
                      className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-red-600"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="space-y-3 rounded-xl border p-4">
            <h2 className="font-semibold">Add a bill</h2>
            <Input placeholder="e.g. Rent, Assistant salary" value={billName} onChange={(e) => setBillName(e.target.value)} />
            <Input
              placeholder="Amount (₹)"
              inputMode="numeric"
              value={billAmount}
              onChange={(e) => setBillAmount(e.target.value)}
            />
            <div className="flex rounded-lg border p-0.5 text-sm">
              {[
                { once: false, label: "Every month" },
                { once: true, label: "One time" },
              ].map((o) => (
                <button
                  key={o.label}
                  type="button"
                  onClick={() => setBillOnce(o.once)}
                  className={
                    "flex-1 rounded-md px-3 py-1.5 " + (billOnce === o.once ? "bg-foreground text-background" : "text-muted-foreground")
                  }
                >
                  {o.label}
                </button>
              ))}
            </div>
            {billOnce ? (
              <Input type="date" value={billDate} onChange={(e) => setBillDate(e.target.value)} />
            ) : (
              <label className="flex items-center gap-2 text-sm">
                <span className="text-muted-foreground">Due on day</span>
                <Input
                  inputMode="numeric"
                  value={billDay}
                  onChange={(e) => setBillDay(e.target.value)}
                  className="w-20"
                />
                <span className="text-muted-foreground">of each month</span>
              </label>
            )}
            <Button
              type="button"
              variant="outline"
              className="w-full"
              disabled={busy || !billName.trim() || !Number(billAmount) || (billOnce && !billDate)}
              onClick={() =>
                run(
                  () =>
                    api("/settings/bills", {
                      method: "POST",
                      body: JSON.stringify({
                        name: billName.trim(),
                        amount: Number(billAmount),
                        recurrence: billOnce ? "once" : "monthly",
                        due_day: Math.min(31, Math.max(1, Number(billDay) || 1)),
                        next_due_date: billOnce ? billDate : null,
                      }),
                    }).then(() => {
                      setBillName("");
                      setBillAmount("");
                      setBillDate("");
                    }),
                  `Added ${billName.trim()}.`,
                )
              }
            >
              Add bill
            </Button>
          </section>

          <section className="rounded-xl border p-4 text-sm text-muted-foreground">
            <p className="font-medium text-foreground">Demo tools</p>
            <p className="mt-1">
              Open the <a className="underline" href="/sms-simulator">SMS simulator</a> to send a test bank message.
            </p>
          </section>
        </>
      )}
    </main>
  );
}
