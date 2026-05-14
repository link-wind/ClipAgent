# Marketing Homepage Hero Refresh Design

Date: 2026-05-14
Repo: `/Users/linkwind/Code/ClipForge_v2`
Scope: `src/components/dashboard/DashboardPage.tsx` homepage refresh for the public-facing product shell

## Goal

Turn the current homepage from an operations-oriented dashboard into a public-facing product homepage that explains ClipForge clearly on first view.

The homepage should present ClipForge as:

`a product-to-video agent that turns product information into an editable video result`

This phase is intentionally focused on the homepage presentation layer only. It does not add new backend data, new APIs, or new product capabilities. The main job is to change the narrative, layout, and visual system of the homepage so the first screen explains the product instead of reading like an internal dashboard.

## Why Now

The current homepage still carries strong dashboard language:

- metrics-first structure
- recent tasks emphasis
- operations-summary composition
- a visual tone closer to an internal console

That was useful when the homepage direction was still "operations overview." The product has since moved toward a hosted, externally understandable experience. For a first-time visitor, the top priority is now:

1. understand what ClipForge is
2. see proof that it produces real video output
3. understand the workflow at a glance

This refresh should make the homepage behave like a product introduction page while still feeling connected to the existing workspace and agent experience.

## Validated Direction

The user confirmed the following design decisions during brainstorming:

- Audience: external users / customers seeing the product
- Primary first-screen task: explain what the product is
- Product framing: a one-stop video agent from product information to final output
- Preferred narrative direction: proof-first homepage with product explanation immediately visible
- Hero split: 50 / 50
- Visual temperature: light, premium, restrained
- Hero order: left side explains the product first, right side shows the output preview

The selected homepage concept is:

`sample-output proof + product definition + short workflow proof`

## Narrative Role

This page is not:

- a pure marketing landing page full of generic claims
- an internal dashboard
- a gallery page for examples only

This page is:

- the product homepage
- the first explanation layer for new visitors
- a bridge between marketing clarity and the actual workspace product

The homepage should feel like a real product shell, not a brochure.

## Step 3a Positioning

### Narrative role

Hero section for first-time understanding. The hero must tell the visitor what ClipForge does before asking them to trust deeper claims.

### Viewing distance

Mostly desktop and laptop first visits. Users will scan quickly, then decide whether to continue downward or click into the workflow.

### Visual temperature

Quiet, premium, lightly technical, visually controlled. The page should feel designed and productized, not playful, loud, or dashboard-heavy.

### Capacity check

The hero should only hold three information layers:

1. one-sentence product definition
2. primary CTA pair
3. three-step workflow proof

The output preview belongs on the right and should reinforce the claim without competing with it for narrative priority.

## Design Decisions

```md
Design Decisions:
- Color palette: warm off-white and cool gray base, deep teal primary, blue-teal secondary, darker tones reserved for video preview zones and primary emphasis
- Typography: tight modern sans for display, neutral readable body copy, firmer treatment for compact labels and numbers
- Spacing system: 8px base grid with 24 / 32 / 40 spacing rhythm in hero surfaces
- Border-radius strategy: 14px to 20px, soft but controlled, avoiding overly playful rounding
- Shadow hierarchy: 2 to 3 light elevation levels, used for separation rather than drama
- Motion style: subtle reveal, low-amplitude float, restrained progress and timeline easing, no flashy transitions
```

## Hero Structure

The validated hero layout is:

### Left column

- eyebrow label describing the product category
- one-sentence product definition
- short supporting paragraph
- primary CTA
- secondary CTA
- three workflow proof cards

### Right column

- large video preview frame
- 3 frame filmstrip or scene strip
- compact output proof metrics
- short proof note that this is generated output, not a static concept image

### Why the order changed

The original proof-first variant placed the sample preview on the left. That was visually attractive but weakened comprehension. The revised layout moves explanation to the left because the user explicitly wants the homepage to explain the product first.

This gives the page:

- clearer scan order
- lower comprehension cost
- better alignment with the product-stage goal

while still keeping the right side visually rich enough to feel like a real video product.

## Section Plan Below the Hero

This phase should set up, and where feasible implement, these homepage sections below the hero:

1. `How it works`
2. `Input / Output`
3. `Example results`
4. `Final CTA`

### 1. How it works

Purpose:

- expand the hero workflow into a more polished explanation
- make the agent flow feel productized rather than like internal task stages

Content shape:

- three horizontally aligned explanation modules on desktop
- each module tied to one part of the product flow
- short product-facing language, not backend vocabulary

Avoid:

- status labels like `queued`, `searching`, `rendering`
- implementation-heavy wording

### 2. Input / Output

Purpose:

- make the product model instantly understandable
- show what the user gives ClipForge and what ClipForge returns

Content shape:

- left side: product URL, audience, selling points, desired style
- right side: script, sourced assets, subtitles, final cut

This section should be visually simple and diagram-like.

### 3. Example results

Purpose:

- ground the page in believable outputs
- prevent the homepage from feeling like a claim-only shell

Content shape:

- 2 to 3 example cards
- each card should feel like a real outcome surface
- examples can remain placeholder-backed in this phase as long as they are clearly structured and not presented as fake testimonials or fabricated social proof

Avoid:

- fake logo walls
- fake customer quotes
- inflated business metrics

### 4. Final CTA

Purpose:

- provide a clean action close after explanation
- route the visitor toward creation or deeper exploration

Content shape:

- one clean headline
- one short support line
- one primary action
- optional secondary action

## Visual Vocabulary to Preserve

The homepage can become more public-facing, but it should still stay sympathetically connected to the existing product shell:

- clean, layered panels
- restrained shadows
- tailwind-based composition already introduced in the repo
- product-like surface treatment rather than illustration-heavy marketing composition

This means:

- no oversized marketing hero card floating in isolation
- no decorative blob gradients
- no purple-pink generic AI palette
- no fake data storytelling

## Changes to Current Homepage

The current `DashboardPage` should be reshaped from metrics-first to narrative-first.

### De-emphasize or remove from the hero

- total sessions
- active tasks
- completed tasks
- failed tasks
- recent task table as a dominant above-the-fold block
- donut breakdown as a primary story element
- ops trend bars as first-screen content

### Keep only if they are repositioned and reframed

- compact proof metrics can survive on the right side if they read like output proof, not operations reporting
- task/workflow concepts can survive if they are rewritten as product workflow explanation

## Content Tone

Copy should feel:

- product-facing
- concise
- confident
- non-hyped

Avoid:

- backend jargon
- orchestration terminology
- vague AI slogans
- marketing exaggeration without proof

Preferred tone examples:

- "把产品 brief 交给 Agent，自动产出可用成片"
- "输入产品信息，输出脚本、素材与成片结果"

Avoid copy shapes like:

- "revolutionize your content pipeline"
- "unlock next-generation AI creativity"

## Implementation Notes

This design is intentionally scoped to the existing homepage file and nearby styling patterns.

Expected implementation target:

- `src/components/dashboard/DashboardPage.tsx`

Implementation should:

- continue the Tailwind-first direction already established for the page
- keep changes tightly scoped to homepage composition and supporting presentational helpers
- avoid introducing new backend dependencies
- prefer real layout changes over layered decorative wrappers

## v0 Expectations

The first implementation draft should prioritize:

1. hero layout and content order
2. updated palette and surfaces
3. section scaffolding below the hero
4. believable output-preview treatment

It does not need to fully perfect:

- final copy polish
- real sample media sourcing
- all motion states
- final responsive finesse

Those can be refined after the structure is visible.

## Risks and Guardrails

### Risk 1: page still reads like a dashboard

Guardrail:

- hero must not open with metrics
- first headline must define the product

### Risk 2: page becomes generic AI landing page

Guardrail:

- restrained palette
- product-shell structure
- output proof grounded in workflow

### Risk 3: visual proof overwhelms comprehension

Guardrail:

- explanation remains on the left
- preview remains on the right
- text hierarchy stays stronger than decorative content

### Risk 4: too much fake marketing content

Guardrail:

- no fake testimonials
- no fabricated statistics
- no meaningless logo wall

## Acceptance Criteria

This design is successful when:

1. the first screen explains ClipForge clearly without requiring scrolling
2. the page visually reads as a product homepage instead of an internal dashboard
3. the sample preview increases trust without hijacking the narrative order
4. the lower sections continue the same visual system and product logic
5. the implementation remains within homepage scope only

## Out of Scope

This phase does not include:

- redesigning the workspace page
- new backend APIs
- new asset ingestion pipelines
- new analytics or dashboard metrics
- final branded asset sourcing pack
- homepage copy experimentation across many variants

## Next Step

After this spec is approved, the next step is to create the implementation plan and then execute the homepage refresh in code.
