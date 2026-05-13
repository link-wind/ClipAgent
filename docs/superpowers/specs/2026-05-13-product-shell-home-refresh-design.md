# Product Shell And Homepage Refresh Design

## Goal

Build a shared visual shell for ClipForge_v2 that moves the product closer to the provided reference images without changing routing or core workflows. The first phase should establish a consistent desktop top navigation, mobile folded navigation, softer card hierarchy, and a homepage that feels like the entry point for the rest of the product.

## Scope

This phase includes:

- Rebuild `ProductShell` around a desktop top navigation and mobile collapsed navigation.
- Introduce a small set of shared visual tokens for background, card surfaces, borders, shadows, text hierarchy, and navigation states.
- Refresh the dashboard homepage to match the new shell and visual language.
- Make minimal compatibility adjustments in `workspace`, `tasks`, and `settings` so they sit correctly inside the new shell.

This phase does not include:

- Reworking the `workspace` three-column information architecture.
- Redesigning the `tasks` detail modal or task flow logic.
- Changing settings field behavior or adding new runtime controls.
- Adding marketing-only controls such as language switchers or MVP badges.
- Building a larger animation system or page-specific visual effects.

## Reference Translation

The supplied references point to a clear design language:

- A pale cool-white page background rather than flat white.
- White cards with soft blue-gray shadows and light borders.
- Large but controlled corner radii.
- A centered pill navigation with a dark active state.
- Strong product branding at top left.
- Sparse but confident use of status UI at top right.
- More generous spacing than the current interface.

The implementation should borrow this structure and tone, but still feel like an internal workflow tool rather than a marketing landing page.

## Design Decisions

### 1. Shell-first rollout

Use a shell-first approach:

1. Replace the current left rail with a top navigation shell.
2. Introduce shared visual tokens.
3. Refresh the dashboard page to fully use the new shell.
4. Apply only minimal spacing and alignment fixes to the remaining pages.

This avoids building a homepage-specific style that later has to be pulled apart into shared layout code.

### 2. Navigation model

Desktop navigation:

- Left: logo mark, product name, one-line subtitle.
- Center: pill navigation for `总览`, `方案`, `任务`, `设置`.
- Right: minimal status cluster, limited to useful system state and one lightweight utility action or anchor.

Mobile navigation:

- Keep the same information architecture.
- Show brand at top with a menu trigger.
- Open navigation in a drawer or collapsible panel.

### 3. Shared visual language

Base visual system for phase 1:

- Page background: pale cool gray-blue.
- Primary cards: white with soft shadow and light stroke.
- Text hierarchy:
  - dark navy for titles,
  - muted blue-gray for support text,
  - restrained status colors for success, warning, and failure.
- Radius scale:
  - medium for controls,
  - large for main cards,
  - pill radius for nav and compact badges.
- Shadow scale:
  - one soft shadow for standard cards,
  - a slightly stronger shadow for hero or focus surfaces only.

### 4. Homepage direction

The homepage should be the closest page to the first reference:

- A large hero card on the left as the main surface.
- A right-side stack of compact summary cards.
- A clearer process band in the middle of the page.
- A refined default workflow card area below.

The page should feel lighter, calmer, and more productized than the current dashboard while still using the existing data shape.

### 5. Other pages in phase 1

`workspace`, `tasks`, and `settings` should not be redesigned in this phase. They should only be adapted enough to:

- fit naturally under the new top shell,
- preserve readable spacing,
- inherit shared card and text tone where easy,
- avoid layout breakage across desktop and mobile.

## Implementation Plan Shape

### Files to change

Primary files:

- `src/components/layout/ProductShell.tsx`
- `src/app/globals.css`
- `src/components/dashboard/DashboardPage.tsx`

Likely light-touch compatibility updates:

- `src/components/workspace/BriefWorkspacePage.tsx`
- `src/components/tasks/TaskManagerPage.tsx`
- `src/components/settings/SettingsPage.tsx`

### Styling strategy

- Prefer Tailwind in component structure.
- Keep global tokens in `globals.css`.
- Avoid growing `ProductShell.module.css`; phase 1 should move the shell toward the Tailwind-first direction already used elsewhere.

### Responsive behavior

Desktop:

- centered max-width content area,
- fixed top shell,
- generous top padding below shell,
- homepage hero and summary grid visible above the fold on common laptop widths.

Mobile:

- compact header row,
- fold-out navigation,
- single-column homepage stacks,
- no horizontal overflow from pill navigation or summary cards.

## Risks And Mitigations

### Risk: shell changes ripple into every page

Mitigation:

- keep page-level changes minimal outside the dashboard,
- verify each route after shell replacement,
- avoid refactoring page internals during this phase.

### Risk: homepage becomes too decorative

Mitigation:

- maintain operational density,
- use visual polish through spacing and hierarchy rather than oversized illustrations or marketing patterns.

### Risk: desktop reference does not compress well to mobile

Mitigation:

- treat mobile navigation as a separate composition,
- preserve IA rather than literal layout parity.

## Verification

Phase 1 is considered complete when:

- desktop shell clearly matches the reference direction,
- mobile shell remains usable and uncluttered,
- dashboard visually reads as part of the new system,
- `workspace`, `tasks`, and `settings` render cleanly inside the shell,
- build passes,
- key routes can be manually opened and checked:
  - `/`
  - `/workspace`
  - `/tasks`
  - `/settings`

## Recommended Next Step

After this spec is approved, create an implementation plan that starts with shell structure and token work, then completes the homepage refresh, then runs a short compatibility pass on the remaining pages.
