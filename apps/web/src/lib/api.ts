// Shared API client, types and formatting helpers for the Hisaab web app.

export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
export const BUSINESS_NAME = process.env.NEXT_PUBLIC_BUSINESS_NAME || "Priya's Classes";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      // keep status text
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

// ---------- types (match the FastAPI responses) ----------

export type Money = string | number;

export type DuesRow = {
  customer_id: string;
  customer_name: string;
  total_due: Money;
  oldest_due_date: string;
  days_late: number;
  invoice_count: number;
  priority: Money;
};

export type DuesResponse = {
  rows: DuesRow[];
  totals: {
    total_outstanding: Money;
    overdue_count: number;
    collected_this_month: Money;
    recovered_this_month: Money;
  };
};

export type ForecastDay = { date: string; best: Money; likely: Money; worst: Money };

export type Forecast = {
  today: string;
  days_ahead: number;
  start_balance: Money;
  safety_buffer: Money;
  days: ForecastDay[];
  shortfall: { date: string; amount: Money } | null;
  causes: { type: "overdue_invoice" | "bill"; label: string; amount: Money; date: string }[];
  assumptions: string[];
  baseline?: Forecast;
};

export type Customer = {
  id: string;
  name: string;
  phone: string | null;
  guardian_name: string | null;
  monthly_fee: Money;
  due_day: number;
  batch: string | null;
  status: "active" | "paused" | "left";
};

export type WhatIfChange =
  | { type: "delay"; customer_id: string; days: number }
  | { type: "drop"; customer_ids: string[]; from_period: string }
  | { type: "new_bill"; name: string; amount: number; date: string; recurrence: "once" }
  | { type: "new_customer"; name: string; monthly_fee: number; start_period: string };

/** The voice agent (or any page) can drive the forecast what-if by dispatching this window event
 *  with detail {changes}, or by saving changes in sessionStorage under this key before navigating to /forecast. */
export const WHAT_IF_EVENT = "hisaab:what-if";
export const WHAT_IF_STORAGE_KEY = "hisaab:pending-what-if";

// ---------- formatting ----------

export const num = (v: Money | null | undefined): number => (v === null || v === undefined || v === "" ? 0 : Number(v));

const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

/** 120000 -> "₹1,20,000" ; -8500 -> "-₹8,500" */
export function rupees(v: Money | null | undefined): string {
  const n = Math.round(num(v));
  return `${n < 0 ? "-" : ""}₹${inr.format(Math.abs(n))}`;
}

/** Compact axis labels: 8500 -> "₹8.5k", 120000 -> "₹1.2L" */
export function rupeesShort(n: number): string {
  const a = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (a >= 100000) return `${sign}₹${(a / 100000).toFixed(a >= 1000000 ? 0 : 1)}L`;
  if (a >= 1000) return `${sign}₹${(a / 1000).toFixed(a >= 10000 ? 0 : 1)}k`;
  return `${sign}₹${a}`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-12-01" -> "1 Dec" (no timezone shifts) */
export function shortDate(iso: string): string {
  const [, m, d] = iso.slice(0, 10).split("-").map(Number);
  return `${d} ${MONTHS[m - 1]}`;
}

export function ordinal(n: number): string {
  const s = n % 100 >= 11 && n % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th";
  return `${n}${s}`;
}

/** "2026-12" -> next month string from an ISO date: "2026-11-22" -> "2026-12" */
export function nextPeriod(iso: string): string {
  const [y, m] = iso.slice(0, 7).split("-").map(Number);
  const ny = m === 12 ? y + 1 : y;
  const nm = m === 12 ? 1 : m + 1;
  return `${ny}-${String(nm).padStart(2, "0")}`;
}

export function whatsappUrl(phone: string | null | undefined, text: string): string {
  const digits = (phone || "").replace(/\D/g, "");
  return `https://wa.me/${digits}?text=${encodeURIComponent(text)}`;
}

export function reminderText(opts: {
  guardian?: string | null;
  student: string;
  amount: Money;
  since: string;
  daysLate?: number;
  payUrl?: string;
}): string {
  const hello = opts.guardian ? `Namaste ${opts.guardian},` : "Namaste,";
  const fee = `${opts.student}'s tuition fees of ${rupees(opts.amount)}`;
  const since = shortDate(opts.since);
  const d = opts.daysLate ?? 0;
  const body =
    d <= 5
      ? `just a friendly reminder that ${fee} are due. Please ignore this if already paid.`
      : d <= 15
        ? `a gentle reminder that ${fee} (due since ${since}) are pending. Kindly pay at your earliest convenience.`
        : d <= 30
          ? `${fee} have been pending since ${since}. Could you please let me know by when you can pay?`
          : `this is regarding ${fee}, outstanding since ${since}. Please clear the dues this week, or call me to discuss.`;
  const pay = opts.payUrl ? ` Pay securely here: ${opts.payUrl}` : "";
  return `${hello} ${body}${pay} Thank you - ${BUSINESS_NAME}`;
}
