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
