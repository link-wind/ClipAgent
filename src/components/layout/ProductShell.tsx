'use client';

import type { ReactNode } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import styles from './ProductShell.module.css';

const NAV_ITEMS = [
  { href: '/', label: '总览', shortLabel: 'D' },
  { href: '/workspace', label: '方案', shortLabel: 'W' },
  { href: '/tasks', label: '任务', shortLabel: 'T' },
];

export default function ProductShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className={styles.shell}>
      <aside className={styles.rail} aria-label="主导航">
        <Link href="/" className={styles.logo} aria-label="ClipForge 首页">
          C
        </Link>
        <nav className={styles.nav}>
          {NAV_ITEMS.map((item) => {
            const isActive = item.href === '/' ? pathname === '/' : pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`${styles.navItem} ${isActive ? styles.active : ''}`}
                title={item.label}
              >
                <span>{item.shortLabel}</span>
              </Link>
            );
          })}
        </nav>
      </aside>
      <main className={styles.main}>{children}</main>
    </div>
  );
}
