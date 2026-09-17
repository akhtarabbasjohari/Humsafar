# Humsafar — AI Travel Planning Agent for Askoli Adventure

> *"Plan better. Travel farther."*

Humsafar is an enterprise-grade, autonomous AI travel planning agent designed specifically for **Askoli Adventure** (`askoliadventure.com`), a premier high-altitude trekking and tour operator in Pakistan. It replaces manual website inquiry workflows with an intelligent, grounded, and physically realistic travel planning engine.

---

## Key Capabilities & Architectural Pillars

1. **Live Ground Truth via Custom MCP (`humsafar-data-mcp`)**:
   - Live query interface against `askoliadventure.com` official packages, trek grading, pricing, and regional coverage.
   - Built-in data integrity guard ensuring strict data freshness (rejects stale data $>24$ hours).
   - Never presents unverified figures as confirmed facts; explicit confidence labeling on all routes (`from our official listing` vs `researched just now, unverified, please confirm with our team`).

2. **Multi-Source Web Search Fallback & RAG Vector Store**:
   - Automatic fallback when travelers inquire about destinations serviced by Askoli Adventure that lack pre-packaged catalog tours (e.g. Chitral, Swat, Kumrat, Neelum).
   - Sliding-window text chunking (320 chars, 40 overlap) with FAISS vector embedding ($D=384$) to compact prompt payloads to $<600$ characters, eliminating Groq TPM rate limits.

3. **Dynamic Physical & Logistical Feasibility Engine**:
   - Zero hardcoded static lookup tables.
   - Dynamic physical modeling of mountain road transit speeds (~30–40 km/h), multi-valley transit overhead across expansive regional spans, and high-altitude ascent gradients (>3,000m AMS risk requiring gradual acclimatization pacing).
   - Immediately intercepts physically impossible requests (e.g., K2 in 2 days) with constructive safety advisories and realistic alternatives.

4. **Dual-LLM Architecture with Live Side-by-Side Comparison**:
   - **Primary Cloud**: Groq API (`openai/gpt-oss-120b` or `llama-3.3-70b-versatile`) for ultra-low Time-to-First-Token (TTFT) and high token throughput.
   - **Local Failover / Preprocessor**: Local Ollama instance (`llama3.2:latest`) for offline preprocessing and resilient failover.
   - **Live Comparison Engine**: Simultaneous dual-dispatch with SchemaGuard output validation, automated single-retry self-correction, latency benchmarking, and visual engineer dashboard (`/api/chat/comparison/view/`).

5. **Human-in-the-Loop (HITL) & Strict Privacy Isolation**:
   - A custom-drafted itinerary is **never** final until explicitly reviewed and confirmed by the traveler (`POST /api/itineraries/<id>/approve/`).
   - Guest sessions are ephemeral (session memory only; never persisted to member DB).
   - Authenticated members get full encrypted chat history, multi-session management, and saved itineraries.
   - Company-side inquiry preparation object auto-populates upon approval without manual data re-entry.

6. **Claude/ChatGPT-Style Responsive Frontend**:
   - Built with Next.js 14 App Router, TypeScript, Tailwind CSS, TanStack Query v5, and Zustand.
   - Independent scrolling panes (`overflow-y-auto` on sidebar and conversation list).
   - Adaptive day-by-day stage rendering (cards, timelines, badges).

---

## Quickstart Guide

### Option 1: Docker Compose (Recommended)

To run the entire system (backend, frontend, database, and local networking) in Docker containers:

```bash
# 1. Clone repository and navigate to root
git clone https://github.com/your-org/humsafar.git
cd humsafar

# 2. Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env to set your GROQ_API_KEY

# 3. Launch containers
docker-compose up --build
```

- **Frontend UI**: `http://localhost:3000`
- **Backend DRF API**: `http://localhost:8000`
- **Model Comparison Dashboard**: `http://localhost:8000/api/chat/comparison/view/`
- **Observability Dashboard**: `http://localhost:8000/api/chat/observability/view/`

---

### Option 2: Local Development Setup

#### 1. Backend Setup (Django REST Framework)

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start development server
python manage.py runserver 127.0.0.1:8000
```

#### 2. Frontend Setup (Next.js)

```bash
cd frontend

# Install dependencies
npm install

# Run Jest unit & integration tests
npm test

# Build for production
npm run build

# Start development server
npm run dev
```

Visit `http://localhost:3000` in your browser.

---

## Automated Test Suites

### Backend Tests (pytest)

```bash
cd backend
.\.venv\Scripts\python.exe -m pytest apps/ -v
```

Includes:
- `apps/chat/tests/test_end_to_end_pipeline.py`: True HTTP end-to-end integration test of the complete lifecycle across 6 stages.
- `apps/chat/tests/test_feasibility_engine.py`: Dynamic mountain physics and elevation ascent tests.
- `apps/chat/tests/test_rag_service.py`: Sliding-window chunking, FAISS cosine retrieval, and context compaction tests.
- `apps/chat/tests/test_phase12_model_comparison.py`: Dual-dispatch, SchemaGuard JSON validation, and single-retry recovery tests.
- `apps/chat/tests/test_phase9_persistence_auth.py`: Guest privacy isolation and member persistence tests.

### Frontend Tests (Jest & React Testing Library)

```bash
cd frontend
npm test
```

Verifies:
- TopBar branding and session header rendering.
- Sidebar collapse/expand toggling.
- Interactive chat message submission and real-time UI updates.
- Welcome greeting and expedition card presentation.

---

## API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/guest/` | Create ephemeral guest session (`guest_token`, `session_id`) |
| `POST` | `/api/auth/login/` | Member authentication (JWT access + refresh) |
| `POST` | `/api/chat/sessions/<id>/send/` | Send message to AI planning agent (Header: `X-Guest-Token` or `Bearer`) |
| `POST` | `/api/itineraries/<id>/approve/` | HITL traveler approval gate; returns company inquiry payload |
| `POST` | `/api/chat/comparison/` | Dual-dispatch query comparison (Groq vs. Ollama) with latency metrics |
| `GET` | `/api/chat/comparison/view/` | Visual side-by-side model comparison dashboard |
| `GET` | `/api/chat/observability/logs/` | Queryable telemetry audit trail of agent skill execution |
| `GET` | `/api/chat/observability/view/` | Internal visual observability dashboard |

---

## Git & PR Conventions

- Strictly complies with **Conventional Commits v1.0.0**: `<type>(<optional scope>): <short description>`.
- Audit logs maintained chronologically in `prompts.md`.
