# Agent Instructions — Humsafar

## 1. Project Purpose & Overview
- **Project Name**: Humsafar
- **Tagline**: *"Plan better. Travel farther."*
- **Target Company**: Askoli Adventure
- **Current Live Website**: `askoliadventure.com` (WordPress-based CMS)
- **Deployment Architecture**: Humsafar is a **standalone, independent service** (Next.js frontend + Django REST backend + MCP servers) that can be embedded as a widget on the company site or operated independently. It is **not** a built-in WordPress plugin.
- **Domain Decoupling & Ground Truth Principle**:
  - The live website is built on WordPress, and its domain is subject to migration or change. Therefore, the target URL is fully decoupled and managed via `COMPANY_SITE_URL` (in `.env`), rather than being hardcoded into application logic.
  - All official itinerary and regional coverage data must be fetched **live** from the configured company website (`COMPANY_SITE_URL`, default `https://askoliadventure.com`). There is **no separate internal itinerary database**. The live WordPress site is the single source of truth for tour packages, route itineraries, inclusions, exclusions, and operational regions.

---

## 2. Technology Stack Architecture
1. **Primary LLM**: **Groq API**
   - High-throughput, ultra-low-latency inference for public-facing customer conversations, complex reasoning, itinerary synthesis, and response generation.
2. **Secondary LLM**: **Ollama (Local)**
   - Local small language model used for lightweight preprocessing, intent classification, entity extraction (e.g., dates, group size, budget), prompt sanitation, and internal query routing to conserve API quotas and minimize latency.
3. **Frontend**: **Next.js (React / TypeScript / Tailwind CSS / Zustand / TanStack Query)**
   - Responsive, embeddable chat interface and standalone trip planning workspace.
   - State Architecture: **Zustand** for local client/UI state & auth tokens; **TanStack Query** for asynchronous server state, mutations, caching, and loading/error states.
   - Supports streaming responses, interactive itinerary draft cards, and inquiry submission modals.
4. **Backend**: **Django REST Framework (DRF / Python)**
   - Robust backend handling chat sessions, conversation orchestration, prompt construction, MCP tool invocation, authentication, and structured inquiry dispatch.
5. **Model Context Protocol (MCP) Servers**:
   - `humsafar-data-mcp`: Custom MCP server dedicated to interacting with `askoliadventure.com`.
   - External Web Search MCP (`Brave Search` or `Tavily`): Fallback research integration for broader regional context.
6. **Authentication & Session Model**:
   - Optional **JWT-based Authentication** (`djangorestframework-simplejwt`):
     - **Guests**: Anonymous, session-only chat experience (conversations held in memory/session cache, no persistent database history required).
     - **Registered Users**: Persistent account-linked conversation history, saved draft itineraries, and tracked booking inquiries.

---

## 3. Core Agent Skills
Across the project phases, Humsafar implements and orchestrates the following core skills:

1. `itinerary_lookup`:
   - Search, extract, and parse existing tour packages, daily schedules, trekking grades, pricing, inclusions, and logistics directly from `askoliadventure.com` via `humsafar-data-mcp`.
2. `region_coverage_check`:
   - Verify whether a user's requested region, valley, mountain range, or trail (e.g., Hunza, Skardu, Fairy Meadows, K2 Base Camp, Swat) falls within Askoli Adventure's operational service area.
3. `web_search_fallback`:
   - Activated strictly when a traveler requests a route or destination where no exact matching itinerary exists on `askoliadventure.com`, but the region is confirmed to be covered by the company. Gathers verified regional trek context, seasonal advisories, trail conditions, and elevation profiles via external search.
4. `itinerary_drafting`:
   - Synthesizes personalized, day-by-day travel plans matching the visitor's preferences (duration, fitness level, altitude acclimation needs, budget, group composition) grounded in verified local logistics.
5. `data_freshness_integrity_check`:
   - Inspects and validates the freshness of scraped data and web results. Applies mandatory timestamps to every presented price and schedule. Rejects or flags unverified, outdated, or ambiguous claims.
6. `inquiry_preparation`:
   - Translates an approved itinerary and traveler details into a structured booking inquiry (JSON payload + formatted summary) ready for transmission to the ITP operations and sales team. Unlocked only after explicit traveler approval via the HITL gate.
7. `conversation_memory`:
   - Session-scoped in-context memory service (`ConversationMemoryService`) accumulating traveler preferences (destination, duration, party size, budget, fitness, special logistics) across all conversational turns for guests and authenticated members. Injects contextual memory blocks into prompt synthesis so preferences persist without repetition.
8. `hitl_approval_gate`:
   - Strict human-in-the-loop gate before custom proposals advance to inquiry preparation. Presents clear "Approve Proposal" (styled in Deep Navy `#0F2C3E`) and "Request Changes" choices. Persists approval status in Zustand store (`useAppStore.approvalStatus`). Supports redraft mutation (`useRedraftItineraryMutation`) folding traveler feedback back into the drafting skill and resetting approval to draft.
9. `git_workflow`:
   - Automated git branching, logical committing, and pull request generation strictly enforced starting with Phase 1:
     - **Branch Creation**: For every phase, create a new branch off `main` before making any changes: `phase-N-short-slug` (e.g., `phase-1-backend-auth`).
     - **Conventional Commits**: Commit work in discrete, logical chunks following the **Conventional Commits v1.0.0** specification (`<type>(<optional scope>): <short description>`). Permitted types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`. Header lines must be concise, imperative, lowercase, and without trailing periods.
     - **Pull Request Deliverables**: At the conclusion of each phase, produce a formal PR title and description using Conventional Commits, detailing:
       - **PR Title**: `<type>(<scope>): <summary>`
       - **Type of Change**: `feat` / `fix` / `refactor` / etc.
       - **Summary**: Key changes made in the phase.
       - **Rationale**: Architecture and design justification.
       - **Verification & Testing**: Step-by-step testing commands and verification results.
10. `retrieval_augmented_matching` (Secondary AI Feature):
    - Replaces rigid, keyword-only search in `search_itineraries` with a dense semantic vector retrieval layer backed by a local FAISS index (`faiss.IndexFlatIP`) and dense embeddings ($D=384$).
    - Automatically embeds scraped itinerary documents and user queries, enabling visitors to find the exact official itinerary using loosely worded queries, destination nicknames, partial names, or landmark references (e.g. asking for "K2 base camp" when the catalog package is titled "Concordia Trek", or "Golden Peak" for "Spantik Peak Expedition").
    - Strictly preserves Phase 4 data freshness: retrieved candidates retain original scrape timestamps and source URLs, and continue to be verified against the 1-hour freshness window by `DataIntegrityGuard`.
11. `live_multi_model_comparison`:
    - Routes the exact same traveler inquiry or test query simultaneously to two or more LLM providers (Groq and Ollama) in parallel, rather than using distinct providers solely for segregated tasks.
    - Measures and contrasts wall-clock execution latencies side-by-side with high-precision timing.
    - Hosted strictly within internal evaluation views (`POST /api/chat/comparison/` and `GET /api/chat/comparison/view/`) without exposure to standard site visitors.
12. `output_schema_validation` (Schema Guard & One-Retry Policy):
    - Enforces structural integrity on model outputs via `SchemaGuard` before presentation or downstream processing.
    - Inspects structured schemas (such as `itinerary_draft` requiring non-empty title, destination, duration_days >= 1, realistic price breakdown, non-empty day_by_day stages, and inclusions).
    - Applies a strict single-retry recovery policy: rejects malformed outputs, issues a targeted corrective prompt to the model with failure reasons, and safely falls back to a structured error state if the retry fails, preventing broken responses.
13. `voice_and_document_processing`:
    - Captures browser audio via the `MediaRecorder` API and transcribes speech using Groq Whisper (`whisper-large-v3`) via `POST /api/chat/transcribe/`. Fills the composer as editable text without auto-sending, with visible error states.
    - Validates uploaded travel files (PDF, plain text, PNG, JPEG, WEBP) using binary magic bytes and a strict 10 MB size limit via `POST /api/chat/upload/`. Extracts text (`pypdf`, direct read, OCR), distills key travel facts locally via Ollama (`llama3.2`) before prompting Groq, and scopes documents to sessions (ephemeral in-memory for guests, persisted for members). Attaches explicit provenance labels (`"from your uploaded document"`).
14. `itinerary_pdf_generation`:
    - Server-side PDF export utilizing Python's `reportlab` library via `POST /api/itineraries/export-pdf/` and `GET /api/itineraries/<id>/pdf/`.
    - Generates publication-ready branded PDFs with plan headings, metadata boxes, styled route timeline tables, inclusions/exclusions columns, and high-altitude mountain gear checklists without requiring full page reloads.

---

## 4. MCP Servers Configuration & Tooling
1. **`humsafar-data-mcp` (Custom Company Data MCP Server)**:
   - **Role**: Primary ground-truth data bridge reading live data from `SOURCE_SITE_URL` (configured via `.env`, defaulting to `https://askoliadventure.com`). The hostname is never hardcoded inside scraping logic.
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
   - **Strict Usage Gate**: Used **only** when `humsafar-data-mcp` confirms the region is covered by Askoli Adventure, but no pre-existing packaged itinerary matches the user's specific request.
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
  - `"from our official listing"`: Direct match verified from the configured `SOURCE_SITE_URL` (`askoliadventure.com`).
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
   - **Decoupled SOURCE_SITE_URL**: The scraping engine strictly reads the target host from `SOURCE_SITE_URL` via environment variables (falling back to `COMPANY_SITE_URL` and `https://askoliadventure.com`). The domain is never hardcoded inside parsing or request builders.
   - **Session-Scoped TTL Caching**: The `SessionScopedCache` caches parsed search and regional coverage queries per conversation session with a 5-minute TTL, avoiding repeated scraping calls during a continuous turn.
   - **Graceful Error Handling**: Anti-bot protections (HTTP 403), slow responses, or network timeouts return structured error payloads (`success: False`, `error: "..."`) rather than crashing or hanging the agent runner.
   - **Agent Runner Integration**: `apps.chat.services.agent_runner.HumsafarAgentRunner` acts as the single execution bridge for tool calling from Django views.
7. **Phase 5: Core Chat Flow & Groq LLM Integration**:
   - **Conversational Endpoint (`ChatMessageSendView`)**:
     - Exposed at `POST /api/chat/sessions/<session_id>/send/`.
     - Processes user messages, executes `humsafar-data-mcp` tools (`search_itineraries`), queries Groq LLM with a grounded system prompt, applies `DataIntegrityGuard` presentation enforcement, and persists conversation turns with metadata.
   - **Groq LLM Engine (`services.groq_service`)**:
     - Uses Groq API (`https://api.groq.com/openai/v1/chat/completions`) with `qwen/qwen3.6-27b` (configurable via `GROQ_MODEL` in `.env`).
     - Strictly grounds model responses in live scraped listings from `askoliadventure.com` to prevent hallucinations of pricing or tour dates.
   - **Frontend API Client (`frontend/src/lib/api.ts`) & JWT Storage Strategy**:
     - **Chosen Storage Approach**: Client-side `localStorage` token store (`humsafar_access_token`, `humsafar_refresh_token`, `humsafar_user`) with request interceptor automatically attaching `Authorization: Bearer <accessToken>`. Unauthenticated visitors operate seamlessly as guests without tokens.
     - **Trade-off Analysis**:
       - *Why Chosen*: High developer agility, immediate guest-to-account fluidity without server-side cookie race conditions or cross-origin cookie credentials configuration complexities across different localhost/production ports.
       - *Trade-off*: `localStorage` is accessible to JavaScript and vulnerable to XSS if malicious scripts execute. For production hardening, moving to `httpOnly` secure cookies with server-side refresh rotation is recommended.
    - **Confidence Label UI & Human Feedback**:
      - Next.js frontend renders Phase 4 confidence labels directly (`"from our official listing"`) next to agent replies and within the interactive itinerary artifact card.
      - Active loading state ("Consulting live tour catalog on askoliadventure.com...") and clear error banners on forms and chat turns ensure robust UX.

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

9. **Targeted Entity Scraping, Complete Itinerary Synthesis & Conversational Intent Gating**:
   - **Reasoning Thought Block Sanitization**: `strip_think_tags()` removes `<think>...</think>` internal reasoning traces from Groq reasoning models (`qwen/qwen3.6-27b`, DeepSeek) before messages are returned, persisted, or displayed. Frontend `MessageBubble.tsx` also applies client-side regex stripping as defense-in-depth.
   - **Strict 3-Entity Whitelisting**: `SourceSiteScraper.parse_itineraries_html` strictly extracts and tags items belonging to the three core travel entities: `tour` (`/tours/`), `expedition` (`/expeditions/`), and `destination` (`/destinations/`). Non-travel routes (`/team/`, `/reviews/`, `/testimonials/`, `/author/`, `/category/`, `/feed/`) and personal biographies (e.g. guide profiles or client reviews) are strictly rejected.
   - **Conversational Intent Gating**: Greetings ("hello", "hi", "salaam", "good morning") and small talk ("who are you", "what can you do", "thanks") are detected upfront. The agent responds hospitably via `generate_conversational_reply()` and returns `itinerary: None`, preventing unwanted itinerary cards or scraping runs on casual messages.
   - **Comprehensive Itinerary Synthesis with Missing Details Search**:
     - When an itinerary or trip plan is requested, the output enforces complete coverage:
       1. Detailed Day-by-Day schedule and pacing
       2. Realistic market pricing range and cost breakdown (in PKR and USD)
       3. Detailed Inclusions (licensed mountain guides, Balti porters, all camp meals, 2-person tents, 4x4 jeeps, national park permits, hotel stays)
       4. Detailed Exclusions (international flights, personal evacuation insurance, technical personal gear, visa fees, tips)
       5. Required Equipment & Mountain Gear Checklist (sub-zero sleeping bags, broken-in trekking boots, thermal layers, Category 4 glacier glasses)
       6. Official Booking & Reservation Contact Details (Askoli Adventure / `askoliadventure.com`, noting 6-8 weeks permit lead time).
     - If an official tour listing states "Pricing upon inquiry" or lacks a schedule, `search_missing_details()` performs a targeted web search for the missing logistical components to synthesize a complete, professional proposal.

10. **Core Directory Hub Scraping, Profile Details Modal, Deferred Session Creation & Semantic Chat Titling**:
    - **Focused Directory Hub Scraping**:
      - `humsafar-data-mcp` restricts catalog exploration strictly to the three primary directory hubs (`/expeditions/`, `/tours/`, `/destinations/`) and deep-scrapes their individual package listings (`extract_single_item_details()`), bypassing generic global WordPress search (`/?s=`) to guarantee higher extraction fidelity for schedules, inclusions, and mountain logistics.
      - Scraped single-item pages populate day-by-day itineraries, inclusions, exclusions, and altitude gear checklists directly into ground truth data.
    - **User Profile Modal**:
      - Clicking the traveler profile button in the top navigation bar or sidebar footer triggers `<UserProfileModal>`, surfacing account username, email, phone/WhatsApp, membership status (`Active Member`), and saved itineraries count, with direct sign-out action.
    - **Deferred Session Creation**:
      - Clicking "+ New plan" does not immediately create an empty database record in the chat session history.
      - A new session is lazily initialized on the backend only when the visitor actually transmits their first message, preventing clutter of abandoned placeholder chats.
    - **First-Query Semantic Titling & Interactive Renaming**:
      - `derive_semantic_session_title()` in `apps.chat.views` inspects the user's initial inquiry and matched itinerary entity to name the conversation semantically (e.g. "K2 Base Camp & Concordia Trek", "Hunza Valley Expedition", "Skardu & Deosai Trek").
      - Travelers can inline-edit and rename any conversation directly in the sidebar or top header via pencil action icons, backed by `PATCH /api/chat/sessions/<id>/`.

11. **Comprehensive Rich Text Travel Proposals, Automatic Missing Details Search & Background Multi-Chat Execution**:
    - **Comprehensive Rich Text Formatting**:
      - Replaced disconnected artifact cards (with `• MD`, `Download`, and truncated boxes) with rich, beautifully styled markdown text rendered via `<MarkdownContent />` (`react-markdown` with bespoke brand styling in `#0F2C3E` Deep Navy and `#0D9488` Teal).
      - Every itinerary inquiry produces a complete travel plan containing:
        1. Overview & Altitude profile (e.g. Deosai average 4,114m, optimal summer season).
        2. Clear Day-by-Day Itinerary with transport modes (4x4 jeeps, trekking) and overnight stops.
        3. Itemized Pricing Breakdown: official package status plus realistic market budget ranges (PKR and USD).
        4. Complete Inclusions & Exclusions lists.
        5. Essential Mountain Gear Checklist (boots, -15°C bag, thermal layers, Category 4 glacier glasses).
        6. Official Booking & Reservation Contacts for Indus Trekking and Tours Pakistan.
      - Never displays raw markdown characters (`**`, `*`, `###`) or file format metadata (`• MD`) to visitors.
    - **Automatic Missing Details Search**:
      - Whenever an official package has pricing or duration upon inquiry, `HumsafarAgentRunner.run_multi_hop_pipeline()` automatically invokes `WebSearchService.search_missing_details()` to gather regional logistical facts without requiring explicit user keyword triggers.
    - **Non-Blocking Background Multi-Chat Execution**:
      - `ChatShell` manages messages on a per-session basis (`sessionMessages: Record<string, MessageProps[]>`) and tracks running tasks via `inFlightSessionIds: Set<string>`.
      - When a user submits a query in Chat A and switches to Chat B, Chat A continues executing in the background without state clobbering or interruption.
      - `Sidebar` displays a live animated pulsing indicator next to any session actively running in the background.

12. **Response Formatting & Rendering Skill (Structure is Earned, Not Default)**:
    - **Philosophical Core**:
      - Borrowing from leading conversational products (ChatGPT, Claude, Perplexity), structure in Humsafar is **earned, not default**.
      - Unearned structure (forcing headings, bullet lists, bolded phrases, or itinerary cards into every reply) creates visual clutter, increases cognitive friction, and feels robotic.
      - Plain conversational prose is the gold standard for concise queries. Complex structural elements (timelines, cards, tables, badges) are unlocked only when the information density warrants them.
    - **The Six Non-Negotiable Formatting & Rendering Rules**:
      1. **Rule 1: Plain Conversational Answers for Short Queries**:
         - Short factual or clarifying queries (e.g. *"what dates work for K2 base camp"*, *"what is the elevation of Concordia"*) receive 1–2 plain, warm sentences without unearned headings, bullet lists, or itinerary cards.
         - **DO**: *"The trekking season for K2 Base Camp runs from late June through late August, with July offering the most stable weather and clearest Karakoram views."*
         - **DON'T**: Emitting `### K2 Base Camp Dates` followed by `* Peak Season: July` and an unrequested full itinerary card.
      2. **Rule 2: Bulleted Lists Reserved for Scannable, Parallel Items**:
         - Bulleted lists are used strictly for multi-item collections (>3 items) that travelers must scan in parallel (e.g. mountain packing gear, inclusions, exclusions).
         - If content has only 1–2 items, write it as a natural sentence.
         - Bulleted lists must **never nest more than one level deep**. If sub-items are needed, group them into a comparison table or clean narrative prose.
         - **DO**:
           ```markdown
           - Rigid trekking boots (broken in)
           - Category 4 UV glacier glasses
           - Four-season sleeping bag (-15°C rated)
           ```
         - **DON'T**:
           ```markdown
           - Footwear
             - Boots
               - Laces
                 - Waterproof
           ```
      3. **Rule 3: No Raw Markdown Itinerary Dumps; Render Visual Timeline Cards**:
         - The chat response must **never** be a monolithic markdown dump of day-by-day itinerary tables or lists in chat prose (`| Day 1 | Islamabad to Skardu |`).
         - The backend emits structured itinerary data in the message payload (`day_by_day` array of stages with day numbers, titles, descriptions, and altitudes).
         - The message prose provides warm narrative commentary and highlights directing the traveler to the visual timeline.
         - The frontend renders an interactive visual timeline card (`<ItineraryCard />`) featuring status badges, day stages with numbered markers, route details, and tabs for inclusions and gear.
         - If structured data is absent or malformed, the frontend gracefully falls back to structured prose without crashing.
         - **DO**: Prose commentary highlighting the route + `<ItineraryCard />` component displaying interactive daily stops, duration, and pricing.
         - **DON'T**: A 20-row markdown table dumped directly in the middle of the chat message bubble.
      4. **Rule 4: Comparison Tables Strictly for Side-by-Side Attribute Comparisons**:
         - Comparison tables are reserved exclusively for multi-attribute comparisons between 2 or more distinct packages, regions, or trails (e.g. comparing K2 Base Camp vs Gondogoro La across duration, max altitude, and difficulty).
         - Never use tables for single-column lists or simple facts.
         - In the frontend (`ResponsiveComparisonTable`), tables display cleanly on desktop/tablet viewports and automatically collapse below the mobile breakpoint (`<640px`) into stacked attribute-value cards to eliminate horizontal overflow.
         - **DO**: Comparing K2 Base Camp vs Gondogoro La with uniform attributes (Duration, Strenuousness, Technical Pass, Pricing).
         - **DON'T**: Putting a single tour's daily schedule or packing list into a markdown table.
      5. **Rule 5: UI Action Controls for Traveler Approvals**:
         - Custom drafted itineraries pending traveler approval must display real, prominent UI action buttons ("Approve Proposal" and "Request Changes") inside the visual itinerary card.
         - Never ask the visitor to type "YES" or "NO" in the chat input.
         - "Approve Proposal" persists the itinerary via the Phase 8 HITL endpoint and renders an emerald "Approved by traveler • Saved" confirmation badge.
         - "Request Changes" prefills the chat input with a contextual refinement prompt so the traveler can easily request pacing or logistical adjustments.
         - **DO**: Interactive `<Button variant="approval">Approve Proposal</Button>` and `<Button variant="outline">Request Changes</Button>`.
         - **DON'T**: Text in chat: *"Please type YES to approve this draft or NO to discard."*
      6. **Rule 6: Headings Reserved Exclusively for Multi-Section Long-Form Content**:
         - Headings (`###`) are strictly reserved for extensive, multi-topic travel guides where distinct thematic sections are genuinely required.
         - A 1–2 paragraph answer must never begin with an `## Overview` or `### Summary` heading.
         - **DO**: Plain narrative paragraphs flowing naturally when addressing a single topic.
         - **DON'T**: Adding `### Overview` above a 2-sentence paragraph, followed by `### Conclusion` above a 1-sentence farewell.

13. **Frontend State Management Architecture (Zustand & TanStack Query)**:
    - **Philosophical Core**:
      - Client UI state and asynchronous server state are strictly decoupled into two specialized libraries: **Zustand** for local client/UI state and **TanStack Query (React Query v5)** for server state and cache synchronization.
      - Components never manage manual loading booleans, error strings, or ad-hoc `fetch()` calls. All network requests, retries, and data invalidation flow through TanStack Query query and mutation hooks.
    - **Local Client State (Zustand — `src/store/useAppStore.ts`)**:
      - **Authentication & Guest State**: Manages `accessToken`, `refreshToken`, `user: UserProfile | null`, `guestToken`, and `isGuest`.
      - **Active Chat Context**: Manages `activeSessionId`, `activeChatTitle`, `activeView` (`"chat" | "auth"`), and `isSidebarOpen`.
      - **Background Multi-Chat Execution**: Manages `inFlightSessionIds` (array of session IDs currently processing responses in the background).
      - **Phase 8+ Itinerary Approval Status**: Manages `approvalStatus: Record<string, boolean>` tracking approved itineraries and redraft interaction states.
      - **Persistence**: Auth credentials and active session identifiers are synchronized safely to `localStorage` via Zustand `persist` middleware.
    - **Server State & Cache Layer (TanStack Query — `src/hooks/`)**:
      - **Authentication Mutations (`src/hooks/useAuthMutations.ts`)**:
        - `useLoginMutation()`: Executes login, updates Zustand tokens on success, and invalidates session queries.
        - `useRegisterMutation()`: Executes account creation and updates Zustand store.
        - `useGuestInitMutation()`: Initializes guest session and records guest token.
      - **Chat & Itinerary Queries/Mutations (`src/hooks/useChatQueries.ts`)**:
        - `useSessionsQuery()`: Queries and caches user chat sessions under `["chat-sessions"]`.
        - `useMessagesQuery(sessionId)`: Queries and caches session messages under `["chat-messages", sessionId]`.
        - `useSendMessageMutation()`: Sends messages, manages `isPending` and error states, and invalidates message and session queries.
        - `useCreateSessionMutation()`, `useDeleteSessionMutation()`, `useRenameSessionMutation()`, `useClaimSessionMutation()`.
        - `useItinerariesQuery()`, `useSaveItineraryMutation()`, `useApproveItineraryMutation()`.
    - **Single Source of Truth Auth Synchronization**:
      - The TanStack Query / API request layer (`src/lib/api.ts`) reads `accessToken` and `guestToken` synchronously directly from `useAppStore.getState()`.
      - The `Authorization: Bearer <token>` and `X-Guest-Token: <token>` headers are attached automatically from the Zustand store.
      - On 401 token refresh, `apiRequest` invokes `/api/auth/token/refresh/` and immediately updates the Zustand store via `useAppStore.getState().setTokens(...)`, keeping UI components and network layer 100% in sync with zero token duplication.
14. **Human-in-the-Loop (HITL) Approval Gate & In-Context Memory Architecture (Phase 8)**:
    - **In-Context Conversation Memory (`ConversationMemoryService` — `backend/services/conversation_memory.py`)**:
      - **Universal Memory Scope**: In-context memory operates across a single conversation session for **every visitor**, whether anonymous guest (tracked via `guest_token`) or authenticated member.
      - **Heuristic & Turn-Accumulation Logic**: Analyzes chronological conversation history to extract and maintain traveler constraints:
        - `destination`: Identifies northern regions (Hunza, Skardu, Gilgit, Chitral, Fairy Meadows, etc.) and proper nouns.
        - `duration_days`: Identifies numerical day counts, day ranges, or week specifications.
        - `party_size`: Distinguishes solo travelers, couples, groups, and family configurations with children.
        - `budget_tier`: Classifies budget, moderate, luxury, or explicit currency limits.
        - `fitness_level`: Categorizes leisure, moderate, strenuous, or mountaineering capabilities.
        - `special_requests`: Tracks dietary, transport, or accessibility notes.
      - **Prompt Injection**: Injects `[IN-CONTEXT MEMORY — REMEMBERED TRAVELER PREFERENCES]` into LLM agentic tool loops and multi-hop synthesis so travelers never have to repeat previously stated preferences.
    - **HITL Gated Itinerary Approval Flow (`ItineraryApprovalGate.tsx` & `ChatItineraryRedraftView`)**:
      - **Strict Gating Constraint**: A custom drafted itinerary can **never** advance to official booking inquiry preparation without explicit traveler approval in the chat UI.
      - **Dual-Choice Interface**:
        - **Approve Choice**: Prominently styled in Deep Navy `#0F2C3E` (`bg-[#0F2C3E] text-white hover:bg-[#183D54] font-semibold`).
        - **Request Changes Choice**: Secondary outline button opening an interactive feedback drawer.
      - **State Storage in Zustand (Phase 7 Store)**:
        - The approval status is stored in `useAppStore.getState().approvalStatus: Record<string, boolean>`—**never** in ephemeral component `useState`.
        - Allows approval states to persist across tab switches, session reloads, and rehydrations.
      - **TanStack Query Redraft Mutation (`useRedraftItineraryMutation`)**:
        - When the visitor requests revisions, the client triggers `useRedraftItineraryMutation` (`POST /api/chat/sessions/<session_id>/redraft/`).
        - The backend invokes `HumsafarAgentRunner.redraft_itinerary()`, folding the traveler's feedback into the itinerary drafting skill.
        - The resulting draft resets approval to `status="draft"` (`is_approved=false`) and asks for traveler approval again.
        - On mutation success, TanStack Query invalidates `chat-messages`, `chat-sessions`, and `saved-itineraries`, and resets the Zustand approval status to `false`.
      - **Inquiry Preparation Handoff**:
        - Before approval, inquiry preparation is locked (`Inquiry Prep Locked` badge with lock icon).
        - Upon approval, the gate unlocks the **"Proceed to Inquiry Preparation →"** action, launching the official inquiry preparation modal to transmit verified itinerary specifications to Indus Trekking and Tours.
15. **Persistence & Auth Isolation, Guest Boundary Enforcement & Inquiry Preparation (Phase 9)**:
    - **Guest Ephemeral Boundaries**:
      - Guest sessions are strictly session-only. Nothing guest-related is ever persisted to `ChatMessage` or `SavedItinerary` database tables.
      - In `ChatMessageSendView` and `ChatItineraryRedraftView`, database persistence (`ChatMessage.objects.create()` and `SavedItinerary.objects.update_or_create()`) is gated behind `if session.user:` (authenticated accounts only).
      - For guest visitors, responses are built on-the-fly with synthetic UUIDs directly from pipeline results, keeping client-side state in-memory (Zustand) without leaving persistent footprints in the database.
    - **Itinerary Ownership Isolation**:
      - `ItineraryListCreateView` and `ItineraryDetailView` enforce `permission_classes = [IsAuthenticated]`.
      - Queryset is strictly filtered to `SavedItinerary.objects.filter(user=request.user)`. Legacy query-parameter fallbacks (e.g. `session_id`) have been removed to prevent cross-user data leakage.
      - Users can only ever list, retrieve, or manage their own itineraries; cross-user access attempts return `403 Forbidden`.
    - **Structured Inquiry Object Preparation (`inquiry_service.py`)**:
      - Implemented `build_inquiry_object(itinerary, user, session, additional_notes)` in `backend/services/inquiry_service.py`.
      - Once an itinerary is approved via `ItineraryApproveView`, a structured inquiry object is generated containing:
        - `inquiry_id`: Unique UUID.
        - `status`: `"ready_for_review"`.
        - `visitor`: Visitor profile details (username, email, phone number, registered status) automatically auto-filled from the custom `User` model if authenticated.
        - `itinerary`: Approved route specifications, duration, confidence label, pricing, and day-by-day itinerary data.
        - `session_context`: Chat session metadata and message count.
        - `notes`: Traveler approval notes or feedback.
      - Returned in the approval API response for review by company human staff. Automated form submission is strictly out of scope and prevented.
    - **Frontend Inquiry Modal Integration (`ItineraryApprovalGate.tsx`)**:
      - Displays auto-filled traveler credentials (name, email, phone) from the Zustand user state.
      - Shows structured inquiry ID and review status.
      - Guest users attempting to prepare an inquiry are guided to log in/register first to bind the itinerary to an account.

16. **Tool Call Observability, Queryable Logging & Secondary LLM (Ollama) Integration (Phase 10)**:
    - **Observability Across Every Tool Call (`ToolCallLog` Table — `backend/apps/chat/models.py`)**:
      - Simple, queryable database table recording every tool invocation, itinerary check, region coverage check, external web search, draft generation, and scraped content preprocessing.
      - Schema captures:
        - `session_id`: Associated conversation identifier (guest or authenticated).
        - `timestamp` (`created_at`): Precise UTC execution timestamp.
        - `skill`: The high-level triggering agent skill (`itinerary_lookup`, `region_coverage_check`, `web_search_fallback`, `itinerary_drafting`, `content_cleaning`).
        - `tool_name`: The granular execution step (`search_itineraries`, `check_region_coverage`, `search_web`, `search_external_web`, `draft_itinerary`, `redraft_itinerary`, `clean_scraped_content`).
        - `status`: Execution outcome (`success` or `failed`).
        - `llm_provider`: Concrete LLM model attribution (e.g. `ollama:llama3.2:3b`, `groq:openai/gpt-oss-120b`, or empty for deterministic tools).
        - `input_data` & `output_data`: JSON payloads for arguments and summary outputs.
        - `duration_ms`: Real execution latency in milliseconds.
        - `error_message`: Stack trace or failure description if tool failed.
    - **Queryable API Endpoint & Developer Dashboard (`backend/apps/chat/views.py`)**:
      - **JSON Endpoint**: `GET /api/chat/observability/logs/?session_id=<id>` and `GET /api/chat/sessions/<id>/observability/` returns the session's complete chronological tool call chain for testing and telemetry inspection.
      - **Internal HTML Dashboard**: `GET /api/chat/observability/view/` renders a minimal, brand-styled table view with live session filters, status badges, latency metrics, and expandable payload inspectors.
    - **Ollama Secondary LLM Integration (`backend/services/ollama_service.py`)**:
      - **Concrete Light Task**: Cleans and summarizes raw scraped webpage text (removing nav menus, footers, and HTML noise) before ground-truth facts reach Groq for itinerary synthesis.
      - **Configuration**: Managed via `OLLAMA_BASE_URL` (default `http://localhost:11434`) and `OLLAMA_MODEL` (default `llama3.2:3b`) in `backend/.env` and `backend/.env.example`.
      - **Graceful Degradation**: If the local Ollama daemon is unreachable, the service safely executes heuristic text cleaning and records `status="failed"` with the error reason in the observability table without crashing the agent pipeline.
      - **Dual LLM Orchestration**: Logs explicitly track which LLM handled which step:
        - `ollama:llama3.2` -> Content cleaning & scraping preprocessing.
        - `groq:openai/gpt-oss-120b` -> High-throughput reasoning, conversation synthesis, and custom itinerary drafting.

17. **Groq Rate Limit Prevention, Prompt Compaction & Secondary LLM Failover**:
    - **Root Cause & Rate Limit Analysis**:
      - Groq's on-demand free tier enforces an 8,000 TPM (Tokens Per Minute) limit for `openai/gpt-oss-120b`.
      - Multi-turn chats accumulated thousands of input tokens from old assistant itineraries, paired with 2,000 `max_tokens` allocations, pushing single turns to 6,000–7,500 tokens and triggering repeated HTTP 429 Rate Limit Exceeded errors.
    - **Dynamic Prompt & History Compaction (`compact_conversation_history`)**:
      - Compares recent user turns against conversation history, pruning to the 3 most recent turns.
      - Summarizes and truncates prior assistant messages (stripping verbose markdown route tables, inclusion blocks, and gear checklists), shrinking prompt footprint by >65%.
      - Web research summaries are capped to 1,000 characters of high-density facts.
      - Tuned `max_tokens` budgets: Conversational replies (200), Factual answers (250), Itinerary comparisons (500), Agent tool loop (650), and Custom Itinerary Drafting (950).
    - **Sliding-Window TPM Rate Limiter (`GroqRateLimiter`)**:
      - Thread-safe sliding-window tracker monitoring token expenditure across a 60-second rolling window.
      - Enforces a safe 6,500 TPM ceiling (leaving a 1,500 token buffer below Groq's 8,000 ceiling).
      - Pauses cooperatively for short delays (<= 8s) or signals immediate fallback if TPM budget is depleted.
    - **Adaptive 429 Backoff & Retry-After Parsing (`post_groq_with_retry`)**:
      - Dynamically parses `Retry-After` HTTP headers and JSON error strings (`"Please try again in X.Xs"`).
      - Replaces static retry intervals with exact API-instructed wait times, preventing aggressive retry loops.
      - Raises `GroqRateLimitExceeded` if wait time exceeds 10s to trigger instant failover.
    - **Secondary LLM (Ollama) Failover Engine (`backend/services/ollama_service.py`)**:
      - Dynamic model resolution via `resolve_model()`, automatically mapping aliases (`llama3.2`, `llama3.2:latest`, `llama3.2:3b`) against local `/api/tags` to eliminate 404 Not Found errors.
      - Implemented `generate_completion()` in `OllamaService`: when Groq hits TPM rate limits, Ollama takes over generation locally without user-facing downtime or rate limit errors.
      - All failover generations are logged in `ToolCallLog` with `llm_provider="ollama:llama3.2"`.

18. **Conversational Intent Gating, Parameter Extraction & Prose Grounding**:
    - **Factual Permit & Logistical Intent Gating (`agent_runner.py`)**:
      - Regular expression patterns catch border zone permit, visa, NOC, pass, and logistical inquiries from all traveler personas (e.g. *"Do foreign tourists need a special permit to visit restricted border zones in Gilgit-Baltistan?"*).
      - Answers permit and logistical questions via concise factual replies (`generate_factual_reply`) instead of triggering catalog searches and dumping unrequested tour cards.
    - **Robust Party Size & Parameter Extraction (`itinerary_drafter.py`)**:
      - Evaluates natural language group expressions including `"party of X"`, `"family of X"`, `"group of X"`, `"team of X"`, `"X of us"`, `"we are X"`, and numerical pax declarations.
      - Enforces current-turn precedence before referencing prior conversational history, preventing parameter leakage across turns.
    - **Official Match Prose Sanitization & Ground-Truth Card Single Authority (`agent_runner.py`)**:
      - When an official tour package is identified on `askoliadventure.com`, all unheaded day stages (`Day \d+:`, `- Day \d+:`), hallucinated durations (`Duration: XX days`), and placeholder pricing lines (`Pricing upon inquiry`) are filtered from the conversational prose.
      - Guarantees the verified `ItineraryCard` is the single source of truth for duration, pricing, and daily route stages, eliminating discrepancies between prose text and card elements.
      - Injects duration discrepancy notes when a traveler requests a timeframe differing from the standard catalog itinerary (e.g. 6 days requested vs 14-day standard expedition), highlighting custom tailoring capability.
    - **Calibrated CPU Fallback Performance (`ollama_service.py`)**:
      - Default client timeout set to `45.0s` to accommodate CPU token generation speeds.
      - Drafting fallback tokens calibrated to `200 max_tokens` for sub-15s completions.

19. **Retrieval-Augmented Matching & Semantic Search (Phase 11 — Secondary AI Feature)**:
    - **Philosophical & Operational Context**:
      - Plain keyword matching on titles inevitably misses common user queries where travelers refer to a destination by nickname, geographic feature, or landmark (e.g. asking for "K2 base camp" when the official catalog page is titled "Concordia Trek", or asking for "Golden Peak" when titled "Spantik Peak Expedition").
      - Retrieval-augmented matching serves as the program's secondary AI feature, complementing the primary Groq multi-hop reasoning and local Ollama secondary LLM.
    - **Local Lightweight FAISS Vector Store (`mcp_servers/humsafar_data_mcp/vector_store.py`)**:
      - Uses `faiss.IndexFlatIP` (Cosine similarity over L2-normalized dense embeddings) backed by an in-memory document store.
      - Self-contained, lightweight, fast (<1ms retrieval), zero hosted services or external infrastructure required.
      - Rebuilds and synchronizes seamlessly when documents are updated or rescraped.
    - **Dense Semantic Embedding Generator (`ItineraryEmbeddingEngine`)**:
      - Generates $D=384$ dimensional float32 unit vectors.
      - Encodes comprehensive document representations combining title, summary, region, duration, highlights, day-by-day itinerary schedules, and inclusions.
      - Employs subword character n-gram hashing alongside domain semantic cluster subspace projections, projecting synonymous concepts (e.g., K2/Concordia/Baltoro/Savage Mountain, Spantik/Golden Peak/Chogo Lungma, Passu/Cathedral Spires/Attabad) into aligned coordinate spaces.
    - **MCP Server Scraper Integration (`mcp_servers/humsafar_data_mcp/scraper.py`)**:
      - Whenever a fresh itinerary page is scraped from `SOURCE_SITE_URL` (or loaded via verified official seed items), an embedding is generated and stored in the vector store alongside scraped text and provenance metadata.
      - In `search_itineraries`: incoming visitor queries are embedded and matched against the vector store using cosine similarity (`min_score=0.20`), returning the closest matching candidates.
      - Hybrid scoring fuses keyword matches with dense vector candidates, enabling semantic matches to surface even when exact keyword matches on titles yield zero hits.
    - **Phase 4 Data Freshness Integrity Rule Maintained**:
      - Stored and retrieved embeddings strictly carry their original `scraped_at` timestamp and `source_url`.
      - Retrieval accuracy does **not** exempt candidates from freshness rules.
      - Candidates flow through `DataIntegrityGuard`: if an item's timestamp exceeds the freshness window (3600s), it is flagged with `is_verified=False`, `status="rejected_unverified"`, and unconfirmed pricing disclaimers.
    - **Agent Runner Alignment (`agent_runner.py`)**:
      - `agent_runner.py`'s multi-hop reasoning pipeline (`run_multi_hop_pipeline` and deterministic fallback) recognizes vector-retrieved candidates (`_retrieval_method="vector_store"` or `_retrieval_score >= 0.20`), ensuring semantically matched itineraries are never discarded by rigid keyword filters.

20. **Live Multi-Model Comparison & Output Validation Guard (Phase 12)**:
    - **Program Requirements Compliance**:
      - Fully satisfies the program's live multi-model comparison and output validation requirements.
      - Extends beyond using dual models for disjoint tasks (Groq for reasoning, Ollama for scraping preprocessing): routes the **exact same visitor message or test query** simultaneously to two or more LLM providers (Groq and Ollama) in parallel.
    - **Concurrent Execution Engine (`backend/services/model_comparison_service.py`)**:
      - Coordinates simultaneous execution using Python's `ThreadPoolExecutor(max_workers=2)`.
      - Captures wall-clock execution latencies with sub-millisecond precision (`time.perf_counter()`) for both Groq (`openai/gpt-oss-120b`) and Ollama (`llama3.2`).
      - Computes comparative analytics: faster provider identification, latency delta in milliseconds, speed ratios, and mutual schema validity booleans.
    - **Output Schema Guard & Single-Retry Policy (`backend/services/schema_guard.py`)**:
      - Enforces strict structural schema integrity across both generation paths before presentation.
      - Validates required schemas:
        - `itinerary_draft`: Requires non-empty `title` (>=3 chars), `destination`/`region`, `duration_days` (>=1), concrete `price` or `pricing_breakdown`, non-empty `day_by_day` array of stages with day numbers and titles/descriptions, and `inclusions`.
        - `conversational`: Requires clean prose (>=10 chars) and strictly rejects unstripped `<think>` tags or raw code blocks.
      - **One-Retry Recovery Rule**:
        - If a model's output fails schema validation, the output is rejected and logged.
        - `SchemaGuard.generate_retry_prompt()` synthesizes a targeted corrective re-prompt identifying the exact failed constraints and schema specification.
        - The model is given **one retry attempt**.
        - If the retry response passes schema validation, the result is accepted and marked as `valid_after_retry` (`retry_count=1`).
        - If the retry fails validation again, the service safely falls back to a structured error state (`status="error"`, `error_code="SCHEMA_VALIDATION_FAILED"`, `errors=[...]`) rather than returning a broken or malformed response to callers.
    - **Internal-Only Isolation & Visitor Flow Protection**:
      - The comparison capability is housed strictly within internal developer/evaluation tools:
        - **JSON API**: `POST /api/chat/comparison/` (live comparison execution) and `GET /api/chat/comparison/` (service descriptor).
        - **Interactive HTML Dashboard**: `GET /api/chat/comparison/view/` (side-by-side card inspector with latency badges, status indicators, and payload inspectors).
      - Completely separated from the visitor-facing chat flow (`ChatShell.tsx`), which remains untouched and continues using Groq as primary with Ollama in its Phase 10 preprocessing role.
    - **Observability Integration**:
21. **Voice Input, Document Uploads, and Itinerary PDF Tools (Phase 13)**:
    - **Backend Dependencies (`requirements.txt`)**:
      - `reportlab>=4.2.0`: Programmatic PDF generation engine for publication-ready travel itineraries.
      - `pypdf>=5.0.0`: Secure PDF document text extraction.
      - `pillow>=10.4.0`: Image loading and OCR format validation.
    - **Voice Input & Groq Whisper Audio Transcription**:
      - Captures audio directly in the visitor's browser using the native `MediaRecorder` API (`audio/webm` or `audio/ogg`).
      - Streams the recorded audio blob to `POST /api/chat/transcribe/` in `ChatAudioTranscribeView`.
      - Calls Groq's audio transcription endpoint using model `whisper-large-v3` with the existing `GROQ_API_KEY` (no additional secrets required).
      - Returns transcribed text as plain text.
      - Fills the composer input as editable text; it is **never sent automatically**, ensuring travelers can review, format, or adjust their message prior to transmission.
      - Robust and friendly error reporting for microphone permission denial (`NotAllowedError`), no speech detected, or backend transcription failure.
    - **Document Upload & Local Ollama Distillation**:
      - Dedicated attachment control supporting PDF, plain text (`.txt`), and common image formats (`.png`, `.jpg`, `.jpeg`, `.webp`).
      - Strictly validates actual content types through binary magic bytes (`%PDF-`, PNG, JPEG, WEBP header signatures), rejecting spoofed file extensions.
      - Enforces a hard 10 MB size limit on both client and backend.
      - Extracts textual content via `pypdf`, native UTF-8 decoders, or image OCR (Windows Media OCR / PIL inspection).
      - Pre-distills raw document content into concise travel specifications (dates, destinations, constraints, traveler party details) locally using Ollama (`llama3.2`) before prompting Groq. Raw, bulky extracted files are never sent directly to Groq.
      - Session-scoped storage: guest document records remain strictly ephemeral in memory and are discarded when the session ends; logged-in sessions persist under Phase 9 auth rules.
      - Distinct provenance labeling: distilled user document information is labeled `"from your uploaded document"`, never carrying Phase 4 catalog confidence labels (`"from our official listing"`).
    - **Itinerary PDF Export Service**:
      - Pure Python PDF generation using `reportlab` in `backend/services/pdf_service.py` via `POST /api/itineraries/export-pdf/` and `GET /api/itineraries/<id>/pdf/`.
      - Formatted according to Askoli Adventure brand guidelines (Deep Navy `#0F2C3E` and Teal `#0D9488`).
      - Output documents feature:
        - Prominent plan title and metadata overview box (destination, duration, estimated price, confidence label, official source).
        - Detailed day-to-day route timeline table (day number, stage title, altitude, and trail description).
        - Included vs. excluded services two-column breakdown.
        - High-altitude mountain equipment and safety gear checklist.
      - Small download buttons placed directly next to the existing save button across both drafted and catalog itineraries.
      - Client downloads trigger immediately via blob URLs without full page reloads.
    - **Saved Itinerary System**:
      - For logged-in users, the sidebar provides a dedicated **Saved Expeditions** section listing every Phase 9 persisted itinerary showing name, duration (`X Days`), and destination.
      - Clicking any entry opens a comprehensive popup modal displaying the complete day-to-day route outline, inclusions/exclusions, gear checklist, and the working PDF download button inside the popup.

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
