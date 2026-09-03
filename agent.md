# Agent Instructions — Humsafar

## 1. Project Purpose & Overview
- **Project Name**: Humsafar
- **Tagline**: *"Plan better. Travel farther."*
- **Target Company**: Indus Trekking and Tours Pakistan (ITP)
- **Live Website**: `itp.7scribes.com`
- **Purpose**: Humsafar is an AI travel planning chatbot embedded directly into the official website of Indus Trekking and Tours Pakistan. It assists prospective travelers and trekkers in exploring Pakistan's northern regions, checking route availability, drafting customized itineraries, verifying logistical details, and preparing structured booking inquiries.
- **Ground Truth Principle**: All official itinerary and regional coverage data must be fetched **live** from `itp.7scribes.com`. There is **no separate internal itinerary database**. The live website is the single source of truth for tour packages, route itineraries, inclusions, exclusions, and operational regions.

---

## 2. Technology Stack Architecture
1. **Primary LLM**: **Groq API**
   - High-throughput, ultra-low-latency inference for public-facing customer conversations, complex reasoning, itinerary synthesis, and response generation.
2. **Secondary LLM**: **Ollama (Local)**
   - Local small language model used for lightweight preprocessing, intent classification, entity extraction (e.g., dates, group size, budget), prompt sanitation, and internal query routing to conserve API quotas and minimize latency.
3. **Frontend**: **Next.js (React / TypeScript / Tailwind CSS)**
   - Responsive, embeddable chat interface and standalone trip planning workspace.
   - Supports streaming responses, interactive itinerary draft cards, and inquiry submission modals.
4. **Backend**: **Django REST Framework (DRF / Python)**
   - Robust backend handling chat sessions, conversation orchestration, prompt construction, MCP tool invocation, authentication, and structured inquiry dispatch.
5. **Model Context Protocol (MCP) Servers**:
   - `humsafar-data-mcp`: Custom MCP server dedicated to interacting with `itp.7scribes.com`.
   - External Web Search MCP (`Brave Search` or `Tavily`): Fallback research integration for broader regional context.
6. **Authentication & Session Model**:
   - Optional **JWT-based Authentication** (`djangorestframework-simplejwt`):
     - **Guests**: Anonymous, session-only chat experience (conversations held in memory/session cache, no persistent database history required).
     - **Registered Users**: Persistent account-linked conversation history, saved draft itineraries, and tracked booking inquiries.

---

## 3. Core Agent Skills
Across the project phases, Humsafar implements and orchestrates the following core skills:

1. `itinerary_lookup`:
   - Search, extract, and parse existing tour packages, daily schedules, trekking grades, pricing, inclusions, and logistics directly from `itp.7scribes.com` via `humsafar-data-mcp`.
2. `region_coverage_check`:
   - Verify whether a user's requested region, valley, mountain range, or trail (e.g., Hunza, Skardu, Fairy Meadows, K2 Base Camp, Swat) falls within Indus Trekking and Tours Pakistan's operational service area.
3. `web_search_fallback`:
   - Activated strictly when a traveler requests a route or destination where no exact matching itinerary exists on `itp.7scribes.com`, but the region is confirmed to be covered by the company. Gathers verified regional trek context, seasonal advisories, trail conditions, and elevation profiles via external search.
4. `itinerary_drafting`:
   - Synthesizes personalized, day-by-day travel plans matching the visitor's preferences (duration, fitness level, altitude acclimation needs, budget, group composition) grounded in verified local logistics.
5. `data_freshness_integrity_check`:
   - Inspects and validates the freshness of scraped data and web results. Applies mandatory timestamps to every presented price and schedule. Rejects or flags unverified, outdated, or ambiguous claims.
6. `inquiry_preparation`:
   - Translates an approved itinerary and traveler details into a structured booking inquiry (JSON payload + formatted summary) ready for transmission to the ITP operations and sales team.
7. `git_workflow`:
   - Automated git branching, logical committing, and pull request generation strictly enforced starting with Phase 1:
     - **Branch Creation**: For every phase, create a new branch off `main` before making any changes: `phase-N-short-slug` (e.g., `phase-1-backend-auth`).
     - **Conventional Commits**: Commit work in discrete, logical chunks following the **Conventional Commits v1.0.0** specification (`<type>(<optional scope>): <short description>`). Permitted types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`. Header lines must be concise, imperative, lowercase, and without trailing periods.
     - **Pull Request Deliverables**: At the conclusion of each phase, produce a formal PR title and description using Conventional Commits, detailing:
       - **PR Title**: `<type>(<scope>): <summary>`
       - **Type of Change**: `feat` / `fix` / `refactor` / etc.
       - **Summary**: Key changes made in the phase.
       - **Rationale**: Architecture and design justification.
       - **Verification & Testing**: Step-by-step testing commands and verification results.

---

## 4. MCP Servers Configuration & Tooling
1. **`humsafar-data-mcp` (Custom Company Data MCP)**:
   - **Role**: Primary data bridge to `itp.7scribes.com`.
   - **Key Capabilities / Tools**:
     - `search_itineraries(query, region, duration_days, trek_grade)`: Live query of package listings.
     - `get_itinerary_details(url_or_slug)`: Deep extraction of day-by-day breakdown, prices, inclusions, exclusions, and physical requirements.
     - `check_region_coverage(region_name)`: Checks operational coverage against the company's active destinations.
     - `list_covered_regions()`: Returns all active operational zones and destinations.
2. **External Web Search MCP (`Tavily` or `Brave Search`)**:
   - **Role**: Secondary research fallback.
   - **Strict Usage Gate**: Used **only** when `humsafar-data-mcp` confirms the region is covered by ITP, but no pre-existing packaged itinerary matches the user's specific request.
   - **Constraint**: Must never override, contradict, or substitute official published company itineraries or policies.

---

## 5. Non-Negotiable Operational Guardrails

### A. Human-in-the-Loop (HITL) Rule
- **A custom drafted itinerary must NEVER be treated as final or confirmed until the visitor explicitly approves it.**
- All generated customized schedules must clearly display a draft state (e.g., `[DRAFT - PENDING TRAVELER APPROVAL]`).
- The assistant must explicitly prompt the user to review, modify, or accept the proposed itinerary before advancing to inquiry preparation or booking handoff.

### B. Data Freshness & Grounding Rule
- **Live Scrape First**: The agent must always prefer freshly scraped or freshly searched live data over any internal parametric knowledge.
- **Mandatory Timestamps**: Every itinerary, schedule, seasonal advisory, or price quote presented to a user **must** include an explicit retrieval timestamp (e.g., `Verified live from itp.7scribes.com on 2026-09-03`).
- **No Unverified Claims**: If the agent cannot verify when a piece of data (especially pricing or seasonal departure dates) was published or retrieved, it must **never** present it as confirmed. It must flag it explicitly as an estimate subject to operator confirmation.

---

## 6. Folder Structure & Coding Conventions

### Project Layout
```text
Humsafar/
├── agent.md                   # Persistent instruction file, standards, and workflow rules
├── prompt.md                  # Chronological prompt and action audit log
├── docs/                      # Architectural docs, research, and company assets
│   └── assets/                # Logos, screenshots, and visual assets
├── backend/                   # Django REST Framework backend
│   ├── .gitkeep
│   ├── manage.py
│   ├── config/                # Django project settings & root URLs
│   ├── apps/
│   │   ├── authentication/    # User accounts, JWT auth, visitor sessions
│   │   ├── chat/              # Chat sessions, message history, agent orchestration
│   │   ├── inquiries/         # Booking inquiry models, serializers, notification hooks
│   │   └── mcp_bridge/        # Client interface to humsafar-data-mcp and search MCP
│   ├── requirements.txt       # Python dependencies
│   └── tests/                 # Backend automated test suites
└── frontend/                  # Next.js frontend application
    ├── .gitkeep
    ├── package.json
    ├── tsconfig.json
    ├── src/
    │   ├── app/               # Next.js App Router pages and API routes
    │   ├── components/        # UI components (chat widget, itinerary cards, modals)
    │   ├── hooks/             # Custom React hooks (useChat, useSession)
    │   ├── lib/               # API clients, utilities, and constants
    │   └── types/             # TypeScript definitions and schemas
    └── public/                # Static public web assets
```

### Coding Conventions
- **Backend (Python / Django REST Framework)**:
  - Strict adherence to **PEP 8**.
  - Type annotations on all core service functions and utilities.
  - Thin views, thick services: Business logic belongs in service modules (`services/`), not inside viewsets or models.
  - Explicit DRF serializers for all incoming payloads and outgoing responses.
  - Safe error handling: Catch network/scraping timeouts gracefully and return informative fallback error codes.
- **Frontend (Next.js / TypeScript)**:
  - TypeScript strict mode enabled (`"strict": true`).
  - Clear separation between Server Components and Client Components (`"use client"`).
  - Modern Tailwind CSS utility classes with accessible semantic HTML elements.
  - Modular UI architecture with clear component boundaries.
