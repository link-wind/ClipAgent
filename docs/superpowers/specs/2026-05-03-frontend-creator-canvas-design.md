# Frontend Creator Canvas Design

## Background

ClipForge currently presents the Agent workflow as a dark two-column workbench:

- Left column: conversation history and composer.
- Right column: plan, progress, and result panels.
- Top bar: product name, current step, and status pill.

The current structure is useful, but visually flat. It treats the generated video as a late-stage attachment instead of the center of the creative workflow. The UI also has limited hierarchy between planning, execution, and final output, so users need to read more text than necessary to understand what is happening.

This design refresh keeps the existing Agent workflow and component boundaries, but changes the screen into a creator-oriented canvas where the output preview, active task state, and editing intent are easier to scan.

## Goals

1. Make the generated video feel like the primary creative artifact.
2. Preserve the current Agent workflow: describe request, review plan, confirm, track progress, preview/download result.
3. Improve visual hierarchy without introducing a new application architecture.
4. Keep the UI responsive across desktop and mobile.
5. Reuse the existing Next.js, React, Zustand, and CSS Modules stack.

## Non-Goals

- No new backend behavior.
- No new media editing controls.
- No drag-and-drop timeline.
- No authentication, account, or project management UI.
- No marketing landing page.
- No new icon library dependency in this pass.

## Chosen Direction

Use the **Creator Canvas** direction.

The interface remains a dark professional tool, but shifts from a plain chat console to a creative production surface. The visual language uses a near-black base, warm muted surfaces, restrained gold for primary action and result emphasis, cyan for agent/user activity, and green for success/running state.

This direction was chosen over:

- **Studio Workbench:** safer and denser, but too close to the current UI.
- **Operator Console:** highly readable, but changes the product away from the existing dark creative identity.

## Layout

### Desktop

The root workspace becomes a two-column production layout:

- **Creator canvas:** wide primary area containing result preview, conversation, and composer.
- **Side rail:** narrower column containing execution progress, plan, and clip/result details.

The creator canvas is split vertically:

1. Result preview region.
2. Agent conversation.
3. Composer.

The preview region appears first so the generated video, or the future output state, is always visually prominent. When a video URL exists, the preview displays the real video with controls. When no video exists, it shows an empty result state that communicates what will appear there after generation.

### Mobile

The layout collapses into a single column:

1. Top status bar.
2. Result preview.
3. Conversation and composer.
4. Progress, plan, and result detail panels.

Buttons become full-width where needed, and message bubbles take the full available width to prevent cramped text.

## Components

### `AgentWorkspace`

Responsibilities:

- Keep existing session restore and polling behavior.
- Render the top project bar.
- Render the creator canvas and side rail structure.
- Render the main result preview region above the conversation.
- Continue passing behavior through existing child components.

Visual changes:

- Replace the flat app shell with a subtly layered production surface.
- Use a compact brand mark next to `ClipForge Agent`.
- Keep the status pill visible at the top right on desktop and below the title on narrow mobile screens.

### `ResultPanel`

Responsibilities remain the same:

- Resolve the best available video URL.
- Show session errors.
- Show preview/download actions.
- Show clip details when clips exist.

Visual changes:

- The video preview becomes visually stronger and more stable.
- Output actions become more prominent.
- Clip details become compact repeated rows with clear duration metadata.

Implementation note:

- Keep detailed result metadata in the side rail.
- Render the main preview region from `AgentWorkspace`.
- Extract a small local helper for resolving the best available video URL so the preview and detail panel do not duplicate that logic.

### `AgentChat`

Responsibilities remain the same:

- Create or continue a session.
- Confirm a ready plan.
- Render conversation messages.
- Render the composer and error state.

Visual changes:

- Message bubbles use warmer dark surfaces and clearer user/agent contrast.
- The empty state should align with the creative task rather than appearing as a centered blank page.
- The composer gets stronger containment and clearer action hierarchy.

### `ProgressPanel`

Responsibilities remain the same:

- Display progress percentage.
- Display current status and step.
- Display workflow steps and recent events.

Visual changes:

- Add a compact metric row for values already available from the session, such as progress, scene count, and target duration when a plan exists.
- Use a more expressive progress bar with warm-to-cyan emphasis.
- Present current and recent events as a clear timeline.

### `PlanPanel`

Responsibilities remain the same:

- Show title, style, target duration, scenes, keywords, and search queries.

Visual changes:

- Summary values become compact stat blocks or key-value rows.
- Scenes become better-separated rows with stronger scene title and duration hierarchy.
- Long descriptions and search queries must continue wrapping safely.

## Data Flow

This design does not change frontend data flow.

- `AgentWorkspace` continues reading session state from `useAgentStore`.
- `AgentChat` continues creating, updating, and confirming sessions through `agentApi`.
- Panels continue reading derived session data from the store.
- Polling remains in `AgentWorkspace`.

Extract a small local helper near the agent components for resolving the best available video URL from a session. Use it in both the main preview and `ResultPanel`. Avoid global abstractions beyond that local helper.

## Styling

Use CSS Modules and global CSS variables.

Update `globals.css` with a richer but restrained palette:

- Base background: near black.
- Primary surfaces: dark charcoal.
- Secondary surfaces: warm charcoal.
- Borders: muted warm gray.
- Primary accent: muted gold.
- Secondary accent: cyan.
- Success accent: soft green.
- Error accent: existing red family refined for contrast.

Constraints:

- Border radius remains 8px or less for cards and panels.
- Avoid decorative orb backgrounds.
- Avoid a one-note palette.
- Keep letter spacing at 0.
- Do not scale font sizes with viewport width.
- Define stable dimensions for preview, composer, side rail panels, buttons, and progress elements to prevent layout shift.

## Error Handling

No behavior changes.

- Chat submission and confirmation errors continue to show in `AgentChat`.
- Session-level errors continue to show in `ResultPanel`.
- Restore and polling failures continue to avoid interrupting the user.

Visual updates must preserve clear error contrast and wrapping for long backend messages.

## Accessibility

- Preserve existing semantic sections and `aria-label` usage.
- Keep video controls available through the native `video` element.
- Ensure focus states remain visible for textarea, buttons, and links.
- Maintain sufficient contrast for text, borders, buttons, disabled states, and error states.
- Do not rely on color alone for progress or status; keep labels visible.

## Testing

Verification should cover:

1. `npm run build` for TypeScript and Next.js build validation.
2. Desktop visual check around 1440px width.
3. Tablet/mobile visual check around 900px and 390px width.
4. Empty session state.
5. Active/running session state, using a temporary local fixture or store seed if live backend data is not available.
6. Plan-ready state with confirm button enabled.
7. Completed session with video preview and clip details, using a temporary local fixture or store seed if live backend data is not available.

Temporary fixtures or store seeds must not be committed unless they are added as an intentional test utility.
