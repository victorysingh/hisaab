"use client";

import { useCallback, useEffect, useState } from "react";
import { MessageCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
} from "@/lib/api";

function MarkPaid({ row, onDone }: { row: DuesRow; onDone: () => void }) {
  const [amount, setAmount] = useState(String(Math.round(num(row.total_due))));
  const [method, setMethod] = useState<"cash" | "upi">("upi");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await api("/payments", {
        method: "POST",
        body: JSON.stringify({
          customer_id: row.customer_id,
          amount: Number(amount),
          method,
          source: "manual",
          received_at: new Date().toISOString(),
        }),
      });
      onDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-3 space-y-2 rounded-lg bg-muted/60 p-3">
      <div className="flex items-center gap-2">
        <span className="text-sm">₹</span>
        <Input inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} className="flex-1" />
      </div>
      <div className="flex gap-2">
        {(["upi", "cash"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMethod(m)}
            className={
              "flex-1 rounded-md border px-3 py-1.5 text-sm " +
              (method === m ? "border-foreground bg-background font-medium" : "text-muted-foreground")
            }
          >
            {m === "upi" ? "UPI" : "Cash"}
          </button>
        ))}
      </div>
      {error && <p className="text-xs text-red-700">{error}</p>}
      <Button type="button" className="w-full" disabled={busy || !Number(amount)} onClick={save}>
        {busy ? "Saving…" : `Mark ${rupees(amount)} paid`}
      </Button>
    </div>
  );
}

export default function DuesPage() {
  const [dues, setDues] = useState<DuesResponse | null>(null);
  const [customers, setCustomers] = useState<Map<string, Customer>>(new Map());
  const [open, setOpen] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  const load = useCallback(() => {
    Promise.all([api<DuesResponse>("/dashboard/dues"), api<Customer[]>("/customers")])
      .then(([d, c]) => {
        setDues(d);
        setCustomers(new Map(c.map((x) => [x.id, x])));
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(load, [load]);
  useEffect(() => {
    window.addEventListener("hisaab:data-changed", load);
    return () => window.removeEventListener("hisaab:data-changed", load);
  }, [load]);

  return (
    <main className="mx-auto w-full max-w-md space-y-4 p-4">
      <header>
        <h1 className="text-2xl font-semibold">Dues</h1>
        <p className="text-sm text-muted-foreground">Who owes you, how much, and since when.</p>
      </header>

      {error && (
        <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          Could not load dues: {error}
        </p>
      )}
      {saved && (
        <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{saved}</p>
      )}

      {!dues && !error && <div className="h-64 animate-pulse rounded-xl bg-muted" />}

      {dues && (
        <>
          <section className="grid grid-cols-2 gap-2">
            <div className="rounded-xl border p-3">
              <p className="text-xs text-muted-foreground">Total outstanding</p>
              <p className="mt-1 text-xl font-semibold">{rupees(dues.totals.total_outstanding)}</p>
            </div>
            <div className="rounded-xl border p-3">
              <p className="text-xs text-muted-foreground">Overdue invoices</p>
              <p className="mt-1 text-xl font-semibold">{dues.totals.overdue_count}</p>
            </div>
          </section>

          <section className="rounded-xl border">
            {dues.rows.length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground">Everyone has paid. 🎉</p>
            ) : (
              <ul className="divide-y">
                {dues.rows.map((r) => {
                  const c = customers.get(r.customer_id);
                  return (
                    <li key={r.customer_id} className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-medium">{r.customer_name}</p>
                          <p className="text-xs text-muted-foreground">
                            {c?.batch ? `${c.batch} · ` : ""}since {shortDate(r.oldest_due_date)} · {r.invoice_count}{" "}
                            month{r.invoice_count > 1 ? "s" : ""}
                          </p>
                        </div>
                        <DaysLateBadge days={r.days_late} />
                        <p className="w-20 text-right font-semibold">{rupees(r.total_due)}</p>
                      </div>
                      <div className="mt-2 flex gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant={open === r.customer_id ? "default" : "outline"}
                          onClick={() => setOpen(open === r.customer_id ? null : r.customer_id)}
                        >
                          Mark paid
                        </Button>
                        <a
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
                          className="inline-flex items-center gap-1 rounded-md border px-3 text-sm hover:bg-muted"
                        >
                          <MessageCircle className="h-4 w-4 text-emerald-600" /> Remind
                        </a>
                      </div>
                      {open === r.customer_id && (
                        <MarkPaid
                          row={r}
                          onDone={() => {
                            setOpen(null);
                            setSaved(`Payment recorded for ${r.customer_name}.`);
                            load();
                          }}
                        />
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </>
      )}
    </main>
  );
}
