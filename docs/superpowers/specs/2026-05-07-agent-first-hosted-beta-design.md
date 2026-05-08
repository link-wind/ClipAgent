# ClipForge Agent-First Hosted Beta Design

## Overview

ClipForge's next stage is not a general-purpose public SaaS launch. The near-term goal is a hosted beta that a small number of brand and marketing users can actually try, where the product feels like a real agent rather than a polished shell around a weak planner.

This stage should prioritize agent experience over raw automation. The product promise is:

> A user provides a plain-text product brief, the agent understands the intent, searches for real product visuals, asks the user to confirm the right product assets, and then generates a grounded product-intro video draft.

The primary value is not "one-click perfect final video." The value is that the system appears to genuinely understand the brief, works with real product visuals, and exposes its reasoning through a collaborative flow.

## Product Goal

Build a small-scale, user-facing hosted beta for 10-50 early users that demonstrates three things clearly:

1. The agent can interpret a product-intro brief in a way that feels intelligent.
2. The agent can find real product visuals rather than relying only on generic stock clips.
3. The final draft is grounded in confirmed product visuals instead of a generic template plan.

The beta should be honest about its boundaries. It should promise a high-relevance draft, not a guaranteed production-ready final cut.

## Target Users

The first user segment is:

- Brand operators
- Small marketing teams

This release should not try to serve every creator type. It should optimize for users who need quick product-intro and feature-highlight videos for launches, product marketing, internal pitches, and short-form campaign support.

## Primary Use Case

The first supported use case is:

- Product introduction and feature-highlight videos

Examples:

- "Make a 30-second feature video for our AI meeting assistant."
- "Create a short product overview video for our new SaaS landing page."
- "Show the top three workflow benefits of our design collaboration tool."

This stage should not broaden into general campaign video generation, multi-format brand publishing, or industry-wide creative assistance. The first job is to become convincingly good at one narrow, valuable scenario.

## Core Product Promise

The user input remains intentionally simple:

- Plain-text brief only

The output must:

- Reflect the real product itself
- Use real product visuals when available
- Produce a grounded draft rather than a purely conceptual mood piece

That means the system cannot depend on the user uploading assets in the first stage. Instead, the agent should actively search for real product visuals from public sources and then involve the user in confirming what is correct before planning and rendering proceed.

## Recommended Flow

The recommended first-stage workflow is a search-first grounded flow:

1. User submits a plain-text brief.
2. Agent interprets the brief and extracts structured intent.
3. Agent searches for real product visuals.
4. Agent presents candidate product visuals to the user.
5. User confirms which candidates represent the correct product.
6. Agent generates a grounded plan based on the confirmed visuals.
7. System executes the render workflow and returns a video draft.

This design intentionally places product-visual confirmation before final planning. That ordering is what makes the agent feel credible. If the plan comes first and asset validation comes later, the experience degrades into generic template planning with asset patching.

## Why This Approach

Three approaches were considered:

1. Plan first, then ask for asset confirmation.
2. Search and confirm product visuals first, then generate the plan.
3. Generate the plan and search in parallel.

Approach 2 is the recommended design.

Why:

- The product must feel like it understands the brief.
- The output must show the real product, not just adjacent concepts.
- The highest-risk failure is product mismatch, so that risk should be surfaced before plan generation.
- A visible confirmation step turns agent understanding into something the user can verify.

Approach 1 is simpler but too easy to make feel fake. Approach 3 is powerful long-term but too complex for the first hosted beta.

## Agent Capability Scope

The first-stage agent should focus on five visible capabilities.

### 1. Brief Understanding

The agent should not merely tokenize the input. It should produce a structured understanding that includes:

- What the product is
- What the main selling points are
- Which features matter most
- Who the intended audience is
- What tone or pacing the video should have

The user-facing response should read like an understanding summary, not a silent background parse.

### 2. Real Product Visual Search

The agent should search for the product itself, not only mood clips or stock footage.

Priority search targets include:

- Official website pages
- Product interface screenshots
- Official demo videos
- Official social content
- Third-party review videos or product showcases

The first stage should allow both official and third-party sources because the user explicitly wants broader retrieval coverage.

### 3. Candidate Curation

The agent should transform raw search results into a curated confirmation set. Each candidate should carry enough metadata for the user to decide quickly:

- Preview or frame
- Source domain or platform
- Source type
- Official versus third-party indicator
- Confidence signal

The user should see "candidate product visuals to confirm," not a generic search results page.

### 4. Grounded Planning

Once the user confirms the correct visuals, the plan should be generated around them.

That means:

- Scene ideas should map to confirmed product visuals
- Feature beats should align to actual product screens or moments
- Search and render should continue from grounded assets rather than restarting from generic stock-video logic

This is the step that turns the product from a clever search tool into a real planning agent.

### 5. Explainable Collaboration

The agent should make its reasoning visible enough that the user feels they are collaborating with it. It should explain:

- What it believes the brief means
- Which product visuals it found
- Why it recommends certain assets
- How those assets shape the resulting video structure

The system should not feel like a black-box generator.

## Explicit Non-Goals

The first-stage beta should clearly avoid the following promises:

- Guaranteed final-production quality
- Universal support for every brief
- Fully autonomous no-confirmation generation
- Stable dependence on YouTube or any single third-party video platform
- Broad industry or use-case coverage
- Assumption that every third-party asset is commercially safe to use

Externally, the honest product promise is:

> Generate a high-relevance product video draft grounded in real product visuals.

## Platform Requirements For The Beta

To make this usable by real early users, the workflow needs a minimum product backbone.

### 1. Session And Task Ownership

Users need to be able to return and see:

- Their original brief
- The agent's understanding summary
- Candidate visual sets
- Their confirmation selections
- The grounded plan
- The final result or failure state

Without this, the product remains a one-off demo rather than a usable beta.

### 2. Persistent Candidate Confirmation

The confirmed candidate set is not a temporary UI convenience. It is the grounding layer for the rest of the workflow and must be stored as durable workflow state.

The downstream plan and execution chain should reference this confirmed set directly.

### 3. Source Transparency

Because both official and third-party sources are allowed, each candidate must preserve source metadata:

- Source platform or domain
- Official versus third-party
- Asset type
- Confidence or match rationale

This protects user trust and makes the confirmation step meaningful.

### 4. Artifact Persistence Beyond Local Disk

The current local downloads/output flow is acceptable for development, but a hosted beta needs a path to durable storage for:

- Candidate previews
- Downloaded visual assets
- Render outputs
- Related artifacts used for task playback

Object storage should be the intended destination, even if rollout happens incrementally.

### 5. Productized Failure States

Failures will happen in the first stage. The requirement is not perfect success rate. The requirement is that failures are understandable and actionable.

Users should be able to tell whether failure occurred during:

- Brief understanding
- Product-visual search
- Asset download
- Render execution

The product should guide the next action rather than surface raw technical confusion.

## Data Model Direction

The most valuable asset in this stage is not only the final MP4. The workflow should preserve a chain of intermediate assets:

1. Plain-text brief
2. Structured brief understanding
3. Candidate product visual set
4. User confirmation result
5. Grounded plan
6. Execution artifacts and output
7. Failure diagnostics when applicable

This chain creates:

- Better user trust
- Better recovery and replay
- Better future training and evaluation data for planner quality

## Operational Risk Boundaries

The hosted beta should define honest boundaries around reliability and trust.

### Product-Match Risk

Some product names are ambiguous. Search may return the wrong product, adjacent tools, or low-confidence results. The confirmation step exists to contain this risk.

### Public Visual Availability Risk

Some products simply do not have enough public visuals to support a strong draft. The product should not pretend that search can solve every case.

### Licensing And Reuse Risk

Third-party content may be discoverable without being safely reusable. The first stage must expose source transparency rather than implying blanket rights safety.

### External Provider Reliability Risk

Search and download pipelines that rely on public platforms are inherently unstable. The product experience should not promise fixed SLA on top of YouTube-like dependencies.

### Output Quality Variance

Render quality will still depend heavily on source quality and asset fit. The beta should promise relevance and grounding before it promises polish consistency.

## Architecture Implication

This stage should be treated as an agent workflow built around product-visual grounding, not as a generic render pipeline with a chat shell attached.

The core state transition should be:

`brief -> interpreted brief -> searched candidates -> confirmed candidates -> grounded plan -> execution -> result`

That transition is the central product truth for the hosted beta and should guide backend models, frontend surfaces, task recovery, and future evaluation tooling.

## Success Criteria

The first hosted beta is successful if an early user can:

1. Enter a plain-text product brief.
2. Feel that the agent correctly understands the intent.
3. Review and confirm candidate visuals that actually look like the product.
4. Receive a plan that clearly references the confirmed product visuals.
5. Get a draft output or an understandable failure state.

The beta is not successful merely because the system renders a video. It is successful when the workflow convinces the user that the agent understood the product and built the draft around the right visual grounding.

## One-Sentence Definition

ClipForge's first hosted beta is an agent-first workflow for brand and marketing teams: a user submits a plain-text product brief, the agent searches and confirms real product visuals, and the system produces a grounded product-intro video draft based on those confirmed assets.
