"use client";

import Link from "next/link";
import { MessageSquare, Mic, ShieldCheck } from "lucide-react";
import { LogoMark } from "@/components/logo";

const TRY = [
  "Will I manage rent next month?",
  "What if Kabir pays 15 days late?",
  "Who should I chase today?",
  "Aisha paid 2500 cash",
  "Rohan ne 3000 diye",
];

/** Shown beside the phone-sized app on wide screens, so judges know what to try. Hidden on phones. */
export function SidePanel() {
  return (
    <aside className="fixed left-8 top-1/2 hidden w-80 -translate-y-1/2 space-y-5 xl:block 2xl:left-24">
      <div className="flex items-center gap-2">
        <LogoMark className="h-9 w-9 rounded-[9px] border-2 border-[var(--ink)]" />
        <span className="font-display text-xl font-extrabold">Hisaab</span>
      </div>
      <h2 className="font-display text-4xl font-extrabold leading-[1.02]">
        Other apps make you type the past.{" "}
        <span className="hl">Hisaab tells you the future.</span>
      </h2>
      <p className="text-sm text-black/65">
        A voice-first back office for home tutors: who owes you, will you make rent, and what to do about it.
      </p>

      <div className="brut-card space-y-2 bg-[var(--lime)] p-4">
        <p className="flex items-center gap-2 font-display font-bold">
          <Mic className="h-4 w-4" /> Tap a line to ask
        </p>
        <div className="flex flex-col items-start gap-1.5">
          {TRY.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => window.dispatchEvent(new CustomEvent("hisaab:ask", { detail: { text: t } }))}
              className="rounded-full border-2 border-[var(--ink)] bg-white px-3 py-1 text-left text-xs font-semibold transition-transform hover:-translate-y-0.5"
            >
              &ldquo;{t}&rdquo;
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-2 text-sm">
        <Link href="/sms-simulator" className="brut-btn bg-white">
          <MessageSquare className="h-4 w-4" /> Simulate a bank SMS payment
        </Link>
        <p className="flex items-center gap-2 pt-1 text-black/60">
          <ShieldCheck className="h-4 w-4" /> Demo data only. Nothing is sent without your OK.
        </p>
      </div>
      <p className="text-xs font-semibold text-black/50">Codebenders ACE Builders&apos; Hackathon 2026 · PS1</p>
    </aside>
  );
}
