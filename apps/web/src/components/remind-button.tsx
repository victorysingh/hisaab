"use client";

import { useState } from "react";
import { Loader2, MessageCircle } from "lucide-react";
import { api, reminderText, whatsappUrl, type Money } from "@/lib/api";
import { cn } from "@/lib/utils";

type Props = {
  customerId: string;
  phone?: string | null;
  guardian?: string | null;
  student: string;
  amount: Money;
  since: string;
  daysLate: number;
  label?: string;
  className?: string;
};

/**
 * Opens WhatsApp with a reminder whose tone matches how late the fee is.
 * If Razorpay is set up, a "Pay now" link for the oldest unpaid month is added.
 * Priya always presses send herself.
 */
export function RemindButton({ customerId, phone, guardian, student, amount, since, daysLate, label, className }: Props) {
  const [busy, setBusy] = useState(false);

  async function onClick() {
    // Open the tab first (synchronously) so pop-up blockers allow it, then point it at WhatsApp.
    const tab = window.open("about:blank", "_blank");
    setBusy(true);
    let payUrl: string | undefined;
    try {
      const link = await api<{ url: string }>(`/payment-links/customer/${customerId}`, { method: "POST" });
      payUrl = link.url;
    } catch {
      payUrl = undefined; // Razorpay not configured or unavailable: send the reminder without a link
    } finally {
      setBusy(false);
    }
    const url = whatsappUrl(phone, reminderText({ guardian, student, amount, since, daysLate, payUrl }));
    if (tab) tab.location.href = url;
    else window.location.href = url;
  }

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border bg-background px-3 py-1 text-sm hover:bg-muted disabled:opacity-60",
        className,
      )}
    >
      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageCircle className="h-4 w-4 text-emerald-600" />}
      {label ?? "Remind"}
    </button>
  );
}
