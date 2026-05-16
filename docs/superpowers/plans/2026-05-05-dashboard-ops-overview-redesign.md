# Dashboard Ops Overview Redesign Implementation Plan

> **Status:** Paused. Do not execute this as the next active plan. The homepage was already substantially rebuilt by the Dashboard Tailwind Home work, and the next project stage should focus on Agent reliability, end-to-end execution, and release readiness rather than more homepage polish.

## Current Assessment

The current Dashboard already covers most of the intended operations overview surface:

- Product-first hero with `ClipForge`, primary workspace entry, task management entry, and search.
- Right-side running overview with synchronized dashboard data.
- Key metrics for total sessions, active tasks, completed tasks, and failed tasks.
- Operational proof section with trend visualization, health snapshot, and resource composition.
- Recent work section with task status, current step, session id, and updated time.
- Build-time structural checks in `scripts/check-product-pages.mjs`.
- Tailwind-based page implementation with the legacy `DashboardPage.module.css` removed.

Because of that, further homepage work should be treated as optional polish, not a prerequisite for the next development phase.

## Paused Follow-Ups

These ideas can be revisited later if the product direction asks for more homepage density:

1. Rename the homepage from product overview toward a stricter operations console.
2. Tighten recent task cards into a more queue-like layout.
3. Add richer live dashboard data after the backend exposes real trend/resource numbers.
4. Browser-check desktop and mobile layout after any future visual change.

## Next-Step Decision

Homepage work is intentionally not the next task. The next stage should move back into the core Agent workflow:

1. Confirm the full `/workspace` to `/tasks` to rendered video path works with real services.
2. Improve failure handling for search, download, render, and worker execution.
3. Document and verify local runbook steps for API, worker, Redis, PostgreSQL, FFmpeg, yt-dlp, and frontend.
4. Decide whether to add a fallback asset provider or local material pool before more UI polish.
