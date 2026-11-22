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
    <nav className="fixed inset-x-0 bottom-0 z-40 border-t bg-background/95 backdrop-blur">
      <ul className="mx-auto flex h-16 max-w-md items-stretch justify-around">
        {items.map(({ href, label, icon: Icon }) => {
          const active = href === '/' ? pathname === '/' : pathname.startsWith(href);
          return (
            <li key={href} className="flex flex-1">
              <Link
                href={href}
                aria-current={active ? 'page' : undefined}
                className={
                  'flex flex-1 flex-col items-center justify-center gap-0.5 text-[11px] ' +
                  (active ? 'font-semibold text-primary' : 'text-muted-foreground hover:text-foreground')
                }
              >
                <Icon className={'h-5 w-5 ' + (active ? 'stroke-[2.5]' : '')} />
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
