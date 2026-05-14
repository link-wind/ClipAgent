'use client';

import { useState } from 'react';
import type { ReactNode } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const NAV_ITEMS = [
  { href: '/', label: '总览' },
  { href: '/workspace', label: '方案' },
  { href: '/tasks', label: '任务' },
  { href: '/settings', label: '设置' },
];

export default function ProductShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const mobileNavId = 'product-shell-mobile-nav';

  const isActive = (href: string) =>
    href === '/' ? pathname === '/' : pathname === href || pathname.startsWith(`${href}/`);

  const renderNavLinks = (linkClassName: (active: boolean) => string) =>
    NAV_ITEMS.map((item) => (
      <Link key={item.href} href={item.href} className={linkClassName(isActive(item.href))} aria-label={item.label}>
        {item.label}
      </Link>
    ));

  return (
    <div className="min-h-screen bg-[color:var(--page-bg)] text-ink">
      <header className="sticky top-0 z-30 border-b border-border/80 bg-[color:var(--page-bg)]/92 backdrop-blur">
        <div className="mx-auto flex min-h-16 w-full max-w-[1440px] items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
          <Link href="/" className="text-base font-semibold tracking-[-0.01em] text-ink" aria-label="ClipForge 首页">
            ClipForge
          </Link>

          <nav className="hidden md:block" aria-label="主导航">
            <div className="flex items-center gap-1 rounded-full border border-border bg-white/78 p-1 shadow-[0_12px_32px_rgba(15,35,28,0.07)]">
              {renderNavLinks((active) =>
                `rounded-full px-4 py-2 text-sm font-semibold transition ${
                  active ? 'bg-ink text-white' : 'text-secondary hover:bg-[color:var(--surface-muted)] hover:text-ink'
                }`,
              )}
            </div>
          </nav>

          <div className="flex items-center gap-2">
            <Link
              href="/workspace"
              className="hidden min-h-10 items-center justify-center rounded-full bg-ink px-4 text-sm font-semibold text-white transition hover:opacity-90 sm:inline-flex"
            >
              开始创建
            </Link>
            <button
              type="button"
              aria-label="移动导航"
              aria-controls={mobileNavId}
              aria-expanded={mobileNavOpen}
              onClick={() => setMobileNavOpen((value) => !value)}
              className="inline-flex min-h-10 items-center justify-center rounded-full border border-border bg-white px-4 text-sm font-semibold text-ink transition hover:bg-[color:var(--surface-muted)] md:hidden"
            >
              菜单
            </button>
          </div>
        </div>

        <div
          id={mobileNavId}
          className={`border-t border-border bg-[color:var(--page-bg)] px-4 py-3 md:hidden ${
            mobileNavOpen ? 'block' : 'hidden'
          }`}
        >
          <nav aria-label="移动导航">
            <div className="flex flex-wrap gap-2">
              {renderNavLinks((active) =>
                `rounded-full border border-border px-4 py-2 text-sm font-semibold transition ${
                  active ? 'bg-ink text-white' : 'bg-white text-secondary hover:bg-[color:var(--surface-muted)] hover:text-ink'
                }`,
              )}
            </div>
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1440px] px-4 py-5 sm:px-6 sm:py-6 lg:px-8 lg:py-7">
        {children}
      </main>
    </div>
  );
}
