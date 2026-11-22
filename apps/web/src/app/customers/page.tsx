"use client";

import { useEffect, useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import { Avatar } from "@/components/avatar";
import { api, ordinal, rupees, type Customer } from "@/lib/api";

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[] | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Customer[]>("/customers")
      .then(setCustomers)
      .catch((e: Error) => setError(e.message));
  }, []);

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = (customers || []).filter(
      (c) => !q || c.name.toLowerCase().includes(q) || (c.guardian_name || "").toLowerCase().includes(q),
    );
    const map = new Map<string, Customer[]>();
    for (const c of list) {
      const key = c.batch || "No batch";
      map.set(key, [...(map.get(key) || []), c]);
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [customers, query]);

  const active = (customers || []).filter((c) => c.status === "active").length;

  return (
    <main className="mx-auto w-full max-w-md space-y-4 p-4">
      <header>
        <h1 className="font-display text-3xl font-extrabold">Students</h1>
        {customers && (
          <p className="text-sm text-muted-foreground">
            {active} active · {customers.length - active} left or paused
          </p>
        )}
      </header>

      <Input placeholder="Search by student or parent" value={query} onChange={(e) => setQuery(e.target.value)} />

      {error && (
        <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          Could not load students: {error}
        </p>
      )}
      {!customers && !error && <div className="h-64 animate-pulse rounded-xl bg-muted" />}

      {groups.map(([batch, list]) => (
        <section key={batch} className="brut-card overflow-hidden">
          <h2 className="border-b-2 border-[var(--ink)] bg-[var(--paper)] px-4 py-2 text-sm font-bold">
            {batch} <span className="font-normal text-muted-foreground">({list.length})</span>
          </h2>
          <ul className="divide-y-2 divide-black/10">
            {list.map((c) => (
              <li key={c.id} className="flex items-center gap-3 px-4 py-3">
                <Avatar name={c.name} className={c.status !== "active" ? "opacity-50" : ""} />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{c.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {c.guardian_name || "Parent"} · due on the {ordinal(c.due_day)}
                  </p>
                </div>
                {c.status !== "active" && (
                  <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">{c.status}</span>
                )}
                <p className="text-sm font-semibold">{rupees(c.monthly_fee)}/mo</p>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </main>
  );
}
