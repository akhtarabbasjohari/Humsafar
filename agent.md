# Agent Instructions — Humsafar

## 1. Project Purpose & Overview
- **Project Name**: Humsafar
- **Tagline**: *"Plan better. Travel farther."*
- **Target Company**: Indus Trekking and Tours Pakistan (ITP)
- **Current Live Website**: `itp.7scribes.com` (WordPress-based CMS)
- **Deployment Architecture**: Humsafar is a **standalone, independent service** (Next.js frontend + Django REST backend + MCP servers) that can be embedded as a widget on the company site or operated independently. It is **not** a built-in WordPress plugin.
- **Domain Decoupling & Ground Truth Principle**:
  - The live website is built on WordPress, and its domain is subject to migration or change. Therefore, the target URL is fully decoupled and managed via `COMPANY_SITE_URL` (in `.env`), rather than being hardcoded into application logic.
  - All official itinerary and regional coverage data must be fetched **live** from the configured company website (`COMPANY_SITE_URL`, default `https://itp.7scribes.com`). There is **no separate internal itinerary database**. The live WordPress site is the single source of truth for tour packages, route itineraries, inclusions, exclusions, and operational regions.

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
1. **`humsafar-data-mcp` (Custom Company Data MCP Server)**:
   - **Role**: Primary ground-truth data bridge reading live data from `SOURCE_SITE_URL` (configured via `.env`, defaulting to `https://itp.7scribes.com`). The hostname is never hardcoded inside scraping logic.
   - **Package Location**: `backend/mcp_servers/humsafar_data_mcp/`
     - `cache.py`: Thread-safe session-scoped TTL cache (`SessionScopedCache`, default TTL 5 minutes) preventing redundant page scrapes within the same conversation.
     - `scraper.py`: Resilient web scraping engine parsing WordPress listings, durations, prices, and regional coverage. Fails gracefully with structured error payloads upon timeouts or anti-bot blocks.
     - `server.py`: Standard MCP Server (`mcp.server.mcpserver.MCPServer`) exposing the tools over stdio transport.
   - **Exposed Tools**:
     - `search_itineraries(query: str, session_id: str = "default")`: Live query of package listings, returning titles, durations, prices, highlights, source URL, and `scraped_at` timestamp.
     - `check_region_coverage(destination: str, session_id: str = "default")`: Checks whether a destination falls within the company's serviced regions.
   - **How to Run Locally**:
     ```powershell
     cd backend
     .\.venv\Scripts\python.exe -m mcp_servers.humsafar_data_mcp.server
     ```
   - **Python Agent Runner Integration**:
     - `apps.chat.services.agent_runner.HumsafarAgentRunner` wires the MCP server tools directly into Django backend views and chat processing loops.
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

### B. Data Freshness, Grounding & Integrity Layer (Enforced in Code)
- **Code-Enforced Provenance**: The agent must always attach an explicit `source_url` and a fresh retrieval timestamp (`scraped_at` / `timestamp`) to any price, date, or itinerary detail it shows a visitor, whether retrieved via live scrape or web search fallback.
- **Rejection of Stale or Missing Sources**: Any itinerary, schedule, or pricing claim that cannot be traced to a fresh source (default freshness window: 3600s / 1 hour) is automatically rejected or flagged (`status="rejected_unverified"`). The agent can never silently fall back on older parametric training data.
- **Mandatory Confidence Labels**: Every presented claim or itinerary must carry an explicit confidence label:
  - `"from our official listing"`: Direct match verified from the configured `SOURCE_SITE_URL` (`itp.7scribes.com`).
  - `"researched just now, unverified, please confirm with our team"`: Content synthesized or discovered via web search fallback.
- **API & Database Level Safeguards**: `SavedItinerary` and `ItineraryApproveView` validate source provenance in code. An itinerary lacking a verifiable source URL or carrying a stale timestamp is rejected from traveler approval with HTTP 400 (`MISSING_SOURCE_URL` or `STALE_OR_MISSING_SOURCE_DATA`).
- **Refusal to Confirm Ungrounded Figures**: When specific prices or schedules are asserted without fresh grounding metadata, `DataIntegrityGuard` appends an explicit operator confirmation disclaimer: *(Notice: This detail could not be verified against a fresh live listing. Humsafar refuses to present unverified figures as confirmed facts. Please confirm exact rates with our team.)*

---

## 6. Folder Structure & Coding Conventions

### Project Layout
```text
Humsafar/
├── agent.md                   # Persistent instruction file, standards, and workflow rules
├── prompt.md                  # Chronological prompt and action audit log
├── README.md                  # Project overview and setup documentation
├── .gitignore                 # Git ignore configuration
├── docs/                      # Architectural docs, research, and company assets
│   └── assets/                # Logos, screenshots, and visual assets
├── backend/                   # Django REST Framework backend
│   ├── .venv/                 # Python 3.13 virtual environment
│   ├── manage.py              # Django management utility
│   ├── requirements.txt       # Python dependencies (Django, DRF, SimpleJWT, pytest)
│   ├── pytest.ini             # Pytest runner configuration
│   ├── db.sqlite3             # Local development database (SQLite fallback)
│   ├── config/                # Django project root configuration
│   │   ├── __init__.py
│   │   ├── asgi.py
│   │   ├── settings.py        # Settings with DRF, SimpleJWT, CORS, and dual-DB support
│   │   ├── urls.py            # API routing root
│   │   └── wsgi.py
│   └── apps/                  # Modular Django applications
│       ├── authentication/    # Custom User model, SimpleJWT auth, guest session init
│       │   ├── models.py      # Custom User (UUID pk, email, phone_number)
│       │   ├── serializers.py # UserSerializer, UserRegistrationSerializer, CustomTokenObtainPairSerializer
│       │   ├── views.py       # RegisterView, CustomLoginView, CurrentUserView, GuestSessionInitView
│       │   ├── urls.py        # /api/auth/ endpoints
│       │   └── tests/         # Pytest authentication tests
│       ├── chat/              # Chat sessions and messages
│       │   ├── models.py      # ChatSession (guest/user scoped), ChatMessage
│       │   ├── serializers.py # ChatSessionSerializer, ChatMessageSerializer
│       │   ├── views.py       # ChatSessionListCreateView, ChatSessionDetailView, ChatMessageListCreateView
│       │   ├── urls.py        # /api/chat/ endpoints
│       │   └── tests/         # Pytest session isolation & message tests
│       └── itineraries/       # Itineraries and Human-in-the-Loop approval
│           ├── models.py      # SavedItinerary (draft/approved status, HITL and freshness flags)
│           ├── serializers.py # SavedItinerarySerializer, ItineraryApprovalSerializer
│           ├── views.py       # ItineraryListCreateView, ItineraryDetailView, ItineraryApproveView
│           ├── urls.py        # /api/itineraries/ endpoints
│           └── tests/         # Pytest draft creation and HITL approval tests
│   ├── mcp_servers/           # Custom Model Context Protocol servers
│   │   └── humsafar_data_mcp/ # Live WordPress scraper MCP server
│   │       ├── cache.py       # Session-scoped TTL cache (5 min TTL)
│   │       ├── scraper.py     # Live scraping logic with graceful error handling
│   │       ├── server.py      # MCPServer exposing search_itineraries and check_region_coverage
│   │       └── tests/         # Mocked HTML unit tests
│   └── services/              # Shared backend services
│       └── agent_runner.py    # Python agent runner coordinating MCP tool executions
└── frontend/                  # Next.js frontend application
    ├── package.json
    ├── tsconfig.json
    ├── tailwind.config.ts     # Two-color brand system: Teal #0D9488 & Deep Navy #0F2C3E
    ├── postcss.config.mjs
    ├── public/
    │   └── logo.png           # Humsafar winding river & mountain logo
    └── src/
        ├── app/
        │   ├── layout.tsx     # Root layout with brand typography & metadata
        │   └── page.tsx       # Landing page mounting ChatShell
        ├── components/
        │   ├── ui/            # Reusable atomic design system tokens
        │   │   ├── Button.tsx # Variants: primary send (#0D9488), approval (#0F2C3E), stop, outline, ghost, header
        │   │   ├── ConfidenceChip.tsx # Perplexity-style source chips in #0F2C3E (official vs unverified)
        │   │   └── Input.tsx  # Accessible brand-styled text and password inputs
        │   ├── chat/          # Chat shell components
        │   │   ├── Sidebar.tsx # Collapsible navigation sidebar (pinned, recent plans, user profile)
        │   │   ├── TopBar.tsx  # Minimal top bar with chat title dropdown, live status, share button
        │   │   ├── MessageList.tsx   # 740px capped column with Claude-style rhythm, empty/loading/error states
        │   │   ├── MessageBubble.tsx # Pale teal tint (#F0FDFA) agent bubble, artifact card, streaming cursor
        │   │   ├── ChatInput.tsx     # Sticky composer with + attachments, send & stop buttons
        │   │   └── ChatShell.tsx     # Root interactive chat shell with responsive sidebar & streaming typewriter
        │   └── auth/
        │       └── AuthScreen.tsx    # Frictionless guest entry & account login/register
        └── styles/
            └── globals.css    # White surface base, clean scrollbars, streaming cursor animation
```

### Phase 1 & 2 Architectural Decisions
1. **Database Choice & PostgreSQL Follow-up**:
   - **Current Development Database**: SQLite (`db.sqlite3`). While a PostgreSQL 18 service is running on the host OS, local connections require specific password authentication credentials not pre-configured in environment variables.
   - **PostgreSQL Readiness (Follow-up)**: `backend/config/settings.py` includes built-in dynamic PostgreSQL support. When credentials are provided via `.env` (`DB_ENGINE=postgresql`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`), the backend automatically switches to PostgreSQL without requiring code changes.
2. **App Architecture & Responsibilities**:
   - `apps.authentication`: Scoped to identity, JWT issuance, user registration/login, and ephemeral guest session token generation.
   - `apps.chat`: Scoped to `ChatSession` lifecycle (handling guest-mode fallback as default) and `ChatMessage` storage with tool invocation metadata.
   - `apps.itineraries`: Scoped to `SavedItinerary` synthesis, storing day-by-day JSON plans, data freshness verification timestamps (`source_verified_at`), and the mandatory Human-in-the-Loop approval endpoint (`/approve/`).
3. **Guest Session Lifecycle**:
   - Guests receive an unauthenticated ephemeral session (`is_guest=True`, `user=None`) accompanied by a `guest_token`.
   - Guest sessions are not indexed under any persistent user profile and remain temporary to the browser session.
4. **Frontend Two-Color Brand System & Senior Product Redesign**:
   - **Brand System (Exactly Two Colors + Neutrals)**:
     - **Primary Interactive Color**: Teal `#0D9488` (send button, active states, focus rings, interactive accents).
     - **Deep Navy Color**: `#0F2C3E` (header background, headings, text accents, itinerary approval button, and source confidence chips).
     - **Base Neutral Surface**: Clean White `#FFFFFF` (page background and primary card surfaces).
     - **Agent Message Bubble**: Pale tint of teal `#F0FDFA` with subtle hairline border `#CCFBF1`.
     - **User Message Bubble**: Crisp White `#FFFFFF` with hairline border `#E2E8F0` and subtle elevation.
   - **Phase 2 Redesign Revision Note**:
     - *Why Revised*: The initial scaffold exhibited hallmarks of generic AI templates (7+ competing colors, identical rounded boxes with uniform soft shadows, tracked-out ALL CAPS headers, middot clutter, arrow buttons, and unconstrained message widths).
     - *What Changed*: Stripped out visual noise to a rigorous two-color palette, capped the conversation column to `max-w-[740px]` centered (matching Claude, ChatGPT, and Perplexity), introduced Claude-like generous vertical rhythm between turns, built real-time streaming typewriter feedback with a reactive Stop button, integrated functional Perplexity-style confidence chips in `#0F2C3E` attached to itinerary claims, visually separated the `#0D9488` send button from the `#0F2C3E` approval button, and crafted evocative empty, loading, and error states reflecting the mountain/river brand motif.
5. **Phase 3: Custom humsafar-data-mcp Server & Live Scraping Guardrails**:
   - **Decoupled SOURCE_SITE_URL**: The scraping engine strictly reads the target host from `SOURCE_SITE_URL` via environment variables (falling back to `COMPANY_SITE_URL` and `https://itp.7scribes.com`). The domain is never hardcoded inside parsing or request builders.
   - **Session-Scoped TTL Caching**: The `SessionScopedCache` caches parsed search and regional coverage queries per conversation session with a 5-minute TTL, avoiding repeated scraping calls during a continuous turn.
   - **Graceful Error Handling**: Anti-bot protections (HTTP 403), slow responses, or network timeouts return structured error payloads (`success: False`, `error: "..."`) rather than crashing or hanging the agent runner.
   - **Agent Runner Integration**: `apps.chat.services.agent_runner.HumsafarAgentRunner` acts as the single execution bridge for tool calling from Django views.
7. **Phase 5: Core Chat Flow & Groq LLM Integration**:
   - **Conversational Endpoint (`ChatMessageSendView`)**:
     - Exposed at `POST /api/chat/sessions/<session_id>/send/`.
     - Processes user messages, executes `humsafar-data-mcp` tools (`search_itineraries`), queries Groq LLM with a grounded system prompt, applies `DataIntegrityGuard` presentation enforcement, and persists conversation turns with metadata.
   - **Groq LLM Engine (`services.groq_service`)**:
     - Uses Groq API (`https://api.groq.com/openai/v1/chat/completions`) with `qwen/qwen3.6-27b` (configurable via `GROQ_MODEL` in `.env`).
     - Strictly grounds model responses in live scraped listings from `itp.7scribes.com` to prevent hallucinations of pricing or tour dates.
   - **Frontend API Client (`frontend/src/lib/api.ts`) & JWT Storage Strategy**:
     - **Chosen Storage Approach**: Client-side `localStorage` token store (`humsafar_access_token`, `humsafar_refresh_token`, `humsafar_user`) with request interceptor automatically attaching `Authorization: Bearer <accessToken>`. Unauthenticated visitors operate seamlessly as guests without tokens.
     - **Trade-off Analysis**:
       - *Why Chosen*: High developer agility, immediate guest-to-account fluidity without server-side cookie race conditions or cross-origin cookie credentials configuration complexities across different localhost/production ports.
       - *Trade-off*: `localStorage` is accessible to JavaScript and vulnerable to XSS if malicious scripts execute. For production hardening, moving to `httpOnly` secure cookies with server-side refresh rotation is recommended.
    - **Confidence Label UI & Human Feedback**:
      - Next.js frontend renders Phase 4 confidence labels directly (`"from our official listing"`) next to agent replies and within the interactive itinerary artifact card.
      - Active loading state ("Consulting live tour catalog on itp.7scribes.com...") and clear error banners on forms and chat turns ensure robust UX.

8. **Phase 6: Multi-Hop Reasoning Pipeline, Web Search Fallback & Itinerary Drafting (The Second Path)**:
   - **Multi-Hop Reasoning Architecture**:
     - Sequential decision tree implemented in `backend/apps/chat/services/agent_runner.py`:
       - **Hop 1 (`check_itinerary`)**: Calls `humsafar-data-mcp` `search_itineraries`. Checks relevance to queried destination. If official tour packages exist, returns immediately as Path 1 (`official_match`) with `"from our official listing"`.
       - **Hop 2 (`check_region`)**: Calls `humsafar-data-mcp` `check_region_coverage`. Determines whether destination is in company's serviced regions (Karakoram, Gilgit-Baltistan, Swat, Chitral, Kalash, etc.). If out of coverage, halts with polite boundary response (`out_of_coverage`).
       - **Hop 3 (`search_web`)**: Triggered strictly when region is covered but no direct itinerary exists. Calls `WebSearchService` with constrained query `"{destination} Pakistan travel itinerary trekking tour guide highlights"`. Multi-provider support (SerpAPI, Tavily, Brave, and curated regional fallback).
       - **Hop 4 (`draft_itinerary`)**: Calls `ItineraryDrafter.draft_custom_itinerary()`. Extracts preferences (duration, party size, budget, fitness level), invokes Groq LLM to synthesize day-by-day plan, and routes output through `DataIntegrityGuard` enforcing `CONFIDENCE_UNVERIFIED` (`"researched just now, unverified, please confirm with our team"`), `status="draft"`, and top source citation.
   - **Structured Reasoning Log Trace**:
     - All 4 hops record input, output, timestamps, and status into `reasoning_steps` array. Persisted in `ChatMessage.metadata["reasoning_steps"]` and exposed in API response for Phase 9 hooks and observability.
   - **Frontend Visual Separation**:
     - `MessageBubble.tsx` renders custom proposals with distinct amber framing, an advisory warning badge highlighting unverified pricing, and explicit status labeling separating drafts from official verified company packages.

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
