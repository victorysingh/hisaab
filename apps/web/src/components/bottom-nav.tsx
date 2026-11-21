'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const items = [
  { href: '/', label: 'Home' },
  { href: '/dues', label: 'Dues' },
  { href: '/forecast', label: 'Forecast' },
  { href: '/customers', label: 'Customers' },
  { href: '/settings', label: 'Settings' },
];

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 border-t bg-background">
      <ul className="mx-auto flex h-16 max-w-md items-stretch justify-around">
        {items.map((item) => {
          const active =
            item.href === '/' ? pathname === '/' : pathname.startsWith(item.href);
          return (
            <li key={item.href} className="flex flex-1">
              <Link
                href={item.href}
                aria-current={active ? 'page' : undefined}
                className={
                  'flex flex-1 items-center justify-center text-sm ' +
                  (active ? 'font-semibold text-primary' : 'text-muted-foreground')
                }
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
