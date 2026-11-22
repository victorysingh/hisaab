"use client";

import Link from "next/link";
import { useState } from "react";
import { MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, rupees, shortDate } from "@/lib/api";

type Candidate = {
  invoice_id: string;
  customer_id: string;
  customer_name: string;
  period: string;
  amount: string;
  due_date: string;
  score: number;
};

type IngestResult = {
  status: "matched" | "needs_review" | "unmatched" | "duplicate" | "ignored";
  payment_id?: string;
  confidence?: number;
  customer_name?: string | null;
  candidates?: Candidate[];
  reason?: string;
  parsed: { amount: string; payer_text: string | null; upi_id: string | null; upi_ref: string | null } | null;
};

const ref = () => String(Math.floor(100000000000 + Math.random() * 899999999999));

const PRESETS: { label: string; text: () => string }[] = [
  {
    label: "Rohan pays (known UPI id)",
    text: () =>
      `Rs 3,000.00 credited to A/c XX1234 on 22-11-26 by VPA rohan.sharma@okaxis (UPI Ref No ${ref()}). -HDFC Bank`,
  },
  {
    label: "Kabir pays (name match)",
    text: () =>
      `Dear Customer, Acct XX4321 is credited with ₹2,500.00 on 22-Nov-26 from kabir.mehta.12@ybl. UPI Ref:${ref()} -ICICI`,
  },
  {
    label: "Unclear payer (needs review)",
    text: () => `INR 2500 received from M K via UPI on 22-Nov-26. Ref no ${ref()}. Avl Bal INR 15,420.50`,
  },
  {
    label: "Debit (ignored)",
    text: () => `Rs 450.00 debited from A/c XX1234 on 22-11-26 to VPA swiggy@icici (UPI Ref No ${ref()}).`,
  },
  { label: "OTP (ignored)", text: () => "123456 is your OTP for UPI transaction of Rs 3000. Do not share it." },
];

const STATUS_STYLE: Record<IngestResult["status"], string> = {
  matched: "border-emerald-200 bg-emerald-50 text-emerald-900",
  needs_review: "border-amber-200 bg-amber-50 text-amber-900",
  unmatched: "border-red-200 bg-red-50 text-red-900",
  duplicate: "border-slate-200 bg-slate-50 text-slate-800",
  ignored: "border-slate-200 bg-slate-50 text-slate-800",
};

export default function SmsSimulatorPage() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<IngestResult | null>(null);
  const [confirmed, setConfirmed] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function send(message: string) {
    setBusy(true);
    setError(null);
    setConfirmed(null);
    setResult(null);
    try {
      setResult(await api<IngestResult>("/payments/ingest", { method: "POST", body: JSON.stringify({ text: message }) }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function confirm(invoiceId: string | null) {
    if (!result?.payment_id) return;
    setBusy(true);
    try {
      const r = await api<{ status: string; customer_name?: string | null }>(
        `/payments/${result.payment_id}/confirm-match`,
        { method: "POST", body: JSON.stringify({ invoice_id: invoiceId }) },
      );
      setConfirmed(
        r.status === "matched" ? `Saved as ${r.customer_name}'s payment. Next time it will match automatically.` : "Marked as not a fee payment.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-md space-y-4 p-4">
      <header>
        <h1 className="flex items-center gap-2 font-display text-3xl font-extrabold">
          <MessageSquare className="h-6 w-6" /> SMS simulator
        </h1>
        <p className="text-sm text-muted-foreground">
          Pretend a bank SMS just arrived on Priya&apos;s phone. Hisaab reads it and matches it to a fee.
        </p>
      </header>

      <section className="space-y-2">
        {PRESETS.map((p) => (
          <button
            key={p.label}
            type="button"
            disabled={busy}
            onClick={() => {
              const t = p.text();
              setText(t);
              void send(t);
            }}
            className="brut-card lift w-full px-3 py-2.5 text-left text-sm font-semibold disabled:opacity-50"
          >
            {p.label}
          </button>
        ))}
      </section>

      <section className="space-y-2">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={4}
          placeholder="Or paste any bank SMS here"
          className="w-full rounded-2xl border-2 border-[var(--ink)] bg-white p-3 text-sm"
        />
        <Button type="button" className="w-full" disabled={busy || !text.trim()} onClick={() => send(text)}>
          {busy ? "Reading…" : "Send SMS"}
        </Button>
      </section>

      {error && <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</p>}

      {result && (
        <section className={"pop space-y-3 brut-card p-4 " + STATUS_STYLE[result.status]}>
          <p className="font-semibold">
            {result.status === "matched" && `✓ ${rupees(result.parsed?.amount)} from ${result.customer_name} - marked paid`}
            {result.status === "needs_review" && `${rupees(result.parsed?.amount)} came in from ${result.parsed?.payer_text ?? "someone"}. Whose fee is it?`}
            {result.status === "unmatched" && `${rupees(result.parsed?.amount)} received, but it doesn't look like a fee`}
            {result.status === "duplicate" && "Already recorded (same UPI reference)"}
            {result.status === "ignored" && "Not a payment - ignored"}
          </p>

          {result.parsed && (
            <dl className="grid grid-cols-3 gap-x-2 gap-y-1 text-xs">
              <dt className="opacity-70">Amount</dt>
              <dd className="col-span-2">{rupees(result.parsed.amount)}</dd>
              <dt className="opacity-70">Payer</dt>
              <dd className="col-span-2">{result.parsed.payer_text ?? "-"}</dd>
              <dt className="opacity-70">UPI id</dt>
              <dd className="col-span-2 break-all">{result.parsed.upi_id ?? "-"}</dd>
              <dt className="opacity-70">Reference</dt>
              <dd className="col-span-2">{result.parsed.upi_ref ?? "-"}</dd>
              {result.confidence !== undefined && (
                <>
                  <dt className="opacity-70">Confidence</dt>
                  <dd className="col-span-2">{result.confidence}/100</dd>
                </>
              )}
            </dl>
          )}

          {result.status === "needs_review" && !confirmed && (
            <div className="space-y-2">
              {result.candidates?.map((c) => (
                <Button
                  key={c.invoice_id}
                  type="button"
                  variant="outline"
                  className="w-full justify-between bg-background"
                  disabled={busy}
                  onClick={() => confirm(c.invoice_id)}
                >
                  <span>
                    {c.customer_name} · {shortDate(c.due_date)}
                  </span>
                  <span>{rupees(c.amount)}</span>
                </Button>
              ))}
              <Button type="button" variant="ghost" className="w-full" disabled={busy} onClick={() => confirm(null)}>
                None of these
              </Button>
            </div>
          )}

          {confirmed && <p className="text-sm font-medium">{confirmed}</p>}
        </section>
      )}

      <div className="flex gap-4 text-sm">
        <Link href="/" className="underline">
          Home
        </Link>
        <Link href="/dues" className="underline">
          Dues
        </Link>
        <Link href="/forecast" className="underline">
          Forecast
        </Link>
      </div>
    </main>
  );
}
