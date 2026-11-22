'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Home, IndianRupee, LineChart, Settings, Users } from 'lucide-react';

const items = [
  { href: '/', label: 'Home', icon: Home },
  { href: '/dues', label: 'Dues', icon: IndianRupee },
  { href: '/forecast', label: 'Forecast', icon: LineChart },
  { href: '/customers', label: 'Students', icon: Users },
  { href: '/settings', label: 'Settings', icon: Settings },
];

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed bottom-0 left-1/2 z-40 w-full max-w-md -translate-x-1/2 border-t-2 border-[var(--ink)] bg-white md:border-x-2">
      <ul className="flex h-16 items-center justify-around px-1">
        {items.map(({ href, label, icon: Icon }) => {
          const active = href === '/' ? pathname === '/' : pathname.startsWith(href);
          return (
            <li key={href} className="flex flex-1 justify-center">
              <Link
                href={href}
                aria-current={active ? 'page' : undefined}
                className={
                  'flex flex-col items-center gap-0.5 rounded-xl px-2.5 py-1 text-[11px] font-semibold transition-all ' +
                  (active
                    ? 'border-2 border-[var(--ink)] bg-[var(--lime)] text-[var(--ink)] shadow-[2px_2px_0_var(--ink)]'
                    : 'border-2 border-transparent text-black/55 hover:text-[var(--ink)]')
                }
              >
                <Icon className="h-5 w-5" />
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
