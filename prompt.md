# Prompt & Activity Log — Humsafar

This file serves as a persistent, chronological audit log tracking every user prompt, directive, and meaningful agent-initiated action throughout the lifecycle of the Humsafar project. For each interaction or significant initiative, a dated entry records the input prompt text and a concise summary of the action taken.

---

### [2026-09-03 10:24 PKT] — Phase 0: Project Initialization & Core Directives Setup

**Prompt Text:**
> You are building Humsafar, an AI travel planning chatbot embedded on a trekking and tour company's own website. Tagline: "Plan better. Travel farther." The company for this build is Indus Trekking and Tours Pakistan, and its live site is itp.7scribes.com. All itinerary and region data must be read live from that site, there is no separate itinerary database.
> 
> Do not write any application code in this phase. Only do the following five things:
> 1. Create the project skeleton with two top level folders, backend and frontend, plus a docs folder. Do not scaffold Django or Next.js yet, just the folders.
> 2. Create agent.md at the project root. This is your persistent instruction file for this whole project. Write into it, in your own words but covering everything below: project purpose, tagline, tech stack (Groq API, local Ollama, Next.js, Django REST Framework, custom company data MCP, external web search MCP, optional JWT auth), full skill list (itinerary lookup, region coverage check, web search fallback, itinerary drafting, data freshness and integrity checking, inquiry preparation, and git workflow), two MCP servers, human-in-the-loop rule, data freshness rule, coding conventions, naming, and folder layout.
> 3. Define git workflow as its own skill in agent.md, alongside the others in the skill list above, and apply it automatically starting with the very next phase (branch per phase `phase-N-short-slug`, Conventional Commits v1.0.0, PR title/description).
> 4. Create prompt.md at the project root with a short header explaining what it is.
> 5. Confirm both files exist and paste me their full contents so I can review them before we scaffold any real code.
> 6. Ask me any clarifying questions you have about the stack or rules above before Phase 1, rather than guessing.

**Action Taken:**
Initialized directory skeleton (`backend/`, `frontend/`, `docs/`) with placeholder files, authored `agent.md` defining all required capabilities, MCP servers, HITL/data-freshness rules, conventions, and git workflow embedded directly in the core skills list, initialized `prompt.md` audit log, and presented clarifying questions prior to Phase 1.

---

### [2026-09-03 10:41 PKT] — Phase 1: Django Backend Scaffolding & Authentication

**Prompt Text:**
> Scaffold the Django backend inside /backend using Django REST Framework. Do only the following.
> 1. Set up a Django project with a clean app structure, one app for users and auth, one app for chat sessions, one app for itineraries. Use PostgreSQL if it is available in my environment, otherwise fall back to SQLite for now and note that as a follow up.
> 2. Implement JWT based auth (reuse the same pattern you already know from a typical Django SimpleJWT setup), registration, login, and a guest mode as the default, so an unauthenticated visitor can still start a chat session with no account.
> 3. Create the data models we will need soon: ChatSession, ChatMessage, SavedItinerary, all scoped to a user where relevant, and a guest session should not persist past the browser session.
> 4. Write pytest tests for registration, login, and guest session creation.
> 5. Update agent.md with the final folder layout under backend and any decisions you made (database choice, app names). Append this prompt and your summary to prompt.md.
> 6. Create a branch named phase-1-backend-auth, commit your work following the git workflow skill in agent.md, and end by giving me the PR title and description for this phase.
> Stop here, do not build the frontend or any MCP server yet.

**Action Taken:**
Created `phase-1-backend-auth` branch, scaffolded DRF backend (`apps/authentication`, `apps/chat`, `apps/itineraries`), implemented SimpleJWT auth with guest-mode default, built `User`, `ChatSession`, `ChatMessage`, and `SavedItinerary` models, verified database setup (SQLite fallback with dynamic PostgreSQL readiness), authored and passed 14 pytest test cases, and updated `agent.md`.

---

### [2026-09-03 11:39 PKT] — Phase 2: Next.js Frontend Scaffolding & Design System

**Prompt Text:**
> Scaffold the Next.js frontend inside /frontend. Do only the following.
> 1. Set up the Next.js project and a basic design system, a set of reusable tokens and components (colors, spacing, typography, button variants) using this palette: header #12372A, logo and icon accent #D89B32, page background #FFFDF7, agent message bubble #E8F4EF, user message bubble #FFFFFF, main button #0B6B50, approval button #D89B32.
> 2. Act as a senior product designer who has shipped consumer AI chat products for a decade. Study the layout patterns of ChatGPT, Claude, Perplexity, and Kimi (their overall structure, not their exact visuals) and design an original chat shell for Humsafar that feels intentional and premium, not like a default template. Pay attention to spacing rhythm, a real typographic hierarchy, subtle elevation and borders instead of heavy shadows, and a distinct personality that fits a mountain and travel brand (the logo has a winding road or river motif and a mountain range).
> 3. Build the static chat shell only, header with the Humsafar wordmark and logo, a scrollable message area with placeholder agent and user bubbles in the correct colors, and an input bar with a send button in the main button color. No backend wiring yet, no real messages.
> 4. Add a simple login and guest entry screen consistent with the same design system.
> 5. Update agent.md with the frontend folder layout and any component naming conventions you chose. Append this prompt and your summary to prompt.md.
> 6. Create a branch named phase-2-frontend-design-system, commit your work following the git workflow skill in agent.md, and end by giving me the PR title and description for this phase.

**Action Taken:**
Branched `phase-2-frontend-design-system` stacked on `phase-1-backend-auth`, configured Next.js App Router project with Tailwind tokens matching the exact brand palette (`#12372A`, `#D89B32`, `#FFFDF7`, `#E8F4EF`, `#FFFFFF`, `#0B6B50`), built reusable design primitives (`Button`, `Badge`, `Input`), designed an original mountain expedition chat shell with floating input and prompt chips, integrated sample draft itinerary card with HITL approval button, created dual-mode login/guest entry screen, verified production build (`next build`), and updated `agent.md`.

---

### [2026-09-03 12:00 PKT] — Phase 2 Revision: Senior Product Redesign & Two-Color Brand System

**Prompt Text:**
> I completed Phase 2 already, but the chatbot design does not feel right and needs a real redesign, not a fresh scaffold. Work directly in the branch I currently have checked out, do not create a new branch or PR for this, this is a fix on top of existing work.
> 
> The brand palette has changed to just two colors, teal #0D9488 and deep navy #0F2C3E. Replace any earlier palette tokens with these. White stays as the neutral background and surface color, it is not a brand color, and the agent message bubble should use a pale tint of the teal rather than a separate hue, so the whole interface reads as built from exactly two brand colors plus neutrals.
> 
> Act as a senior product designer with a decade of experience shipping consumer AI chat products. Before changing any code, look at what exists right now in /frontend and tell me plainly what makes it read as a generic AI generated template rather than a distinct product. Common tells to check for specifically: identical rounded cards with the same soft grey shadow on everything regardless of hierarchy, tracked out ALL CAPS labels above headings, meta text joined with middot dots or em dashes, and arrows appended to button text. Call out anything from that list you find, plus anything else that feels templated.
> 
> Then redesign against these principles and this two color system: header and text accents in #0F2C3E, primary interactive color in #0D9488, white as the base surface, a pale tint of #0D9488 for the agent bubble.
> 1. Cap the message column width to roughly 720 to 768px and center it, the way ChatGPT, Claude, and Perplexity all do, rather than letting messages stretch edge to edge.
> 2. Differentiate user and agent messages primarily through spacing and alignment, not just bubble color, since you now only have one tint to work with for the agent side. Look at how Claude.ai handles this, generous vertical rhythm between turns, a consistent left edge for agent replies, so a long conversation stays easy to scan rather than turning into a wall of boxes.
> 3. Add a visible streaming state, text should appear to type in with a subtle cursor or pulse rather than snapping in all at once, plus a stop button that appears only while a response is generating.
> 4. Turn the confidence label from Phase 4, "from our official listing" versus "researched just now, unverified, please confirm with our team," into a small inline chip in #0F2C3E attached to the relevant itinerary or price, the way Perplexity attaches source chips to claims.
> 5. Give the composer, the message input bar, real presence: comfortable padding, a clear focused state, the send button in #0D9488, and a disabled or stop state while a response is streaming.
> 6. Make the approval button, #0F2C3E, visually distinct from the main send button, #0D9488, since a visitor needs to instantly tell "send a message" apart from "approve this itinerary" even though both now come from the same two color system.
> 7. Design real error, empty, and loading states in the same two color language, not a plain browser default or a generic spinner. An empty new chat state should feel like an invitation to start planning a trip, tying back to the mountain and river motif in the logo, not a blank white box.
> 8. One deliberate, restrained motion moment is welcome, for example how the message list settles when a new reply streams in, but do not add fade and slide animations to every element.
> 
> Work in two passes. First, give me a short before and after plan, what specifically changes and why, referencing the two color system above. Then implement it. Keep it responsive down to mobile width, and keep visible keyboard focus states intact.
> 
> When you are done, commit your changes to the current branch using the Conventional Commits convention I already gave you, a fix or refactor type with a frontend scope is appropriate here since this is correcting Phase 2's output rather than adding new functionality. Update agent.md with the new two color palette and a short note that Phase 2's design was revised here and why, and append this prompt and a summary of what changed to prompt.md.

**Action Taken:**
Audited and called out generic AI template tells across the initial scaffold, defined a two-pass before-and-after redesign plan, overhauled the frontend into a strict two-color brand system (Teal `#0D9488` and Deep Navy `#0F2C3E` on clean white `#FFFFFF`), capped the conversation column to `max-w-[740px]` centered, established Claude-style generous vertical spacing between turns, built real-time streaming typewriter simulation with dynamic Stop button, created Perplexity-style ConfidenceChip in `#0F2C3E` attached to itinerary listings, crafted distinct `#0F2C3E` approval buttons vs `#0D9488` send buttons, designed evocative mountain/river empty states, loading states, and inline error states, verified production build (`next build`), and updated `agent.md`.
