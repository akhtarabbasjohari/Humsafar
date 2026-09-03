# Humsafar: AI Travel Planning Chatbot

> *"Plan better. Travel farther."*

Humsafar is an intelligent, embedded AI travel planning chatbot designed for **Indus Trekking and Tours Pakistan (ITP)** (`itp.7scribes.com`). It helps travelers explore Pakistan's northern mountain regions, check live route availability, synthesize personalized itineraries, verify logistical details, and prepare structured booking inquiries.

---

## Key Highlights

- **Live Ground Truth**: All official itineraries, schedules, trek grades, and regional coverage are queried live from `itp.7scribes.com`. There is no separate or outdated itinerary database.
- **Human-in-the-Loop (HITL)**: Custom-drafted itineraries are treated as drafts until explicitly reviewed and approved by the traveler.
- **Strict Data Freshness**: Every price quote and itinerary route presented to the user is timestamped with its live retrieval time. Unverified or stale data is never presented as confirmed.
- **Dual LLM Architecture**: Combines ultra-low-latency Groq API inference for traveler interactions with a local Ollama instance for lightweight query preprocessing and intent classification.

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | Next.js (App Router), TypeScript, Tailwind CSS | Responsive chat widget, interactive itinerary cards, inquiry modals |
| **Backend** | Django REST Framework (DRF), Python | API services, conversation orchestration, prompt management, JWT auth |
| **Primary LLM** | Groq API | Customer-facing dialogue, itinerary synthesis, and reasoning |
| **Secondary LLM** | Ollama (Local) | Fast preprocessing, entity extraction, and query routing |
| **Data MCP** | `humsafar-data-mcp` | Custom MCP server interfacing with `itp.7scribes.com` |
| **Search MCP** | Brave Search / Tavily MCP | External research fallback when regions are covered but itineraries don't exist |
| **Authentication**| SimpleJWT | Optional auth: session-only for guests, persistent history for members |

---

## Project Structure

```text
Humsafar/
├── agent.md             # Persistent instruction file, skills, and operational rules
├── prompt.md            # Chronological audit log of user prompts and system actions
├── README.md            # Project overview and setup documentation
├── docs/                # Architecture docs, guides, and brand assets
│   └── assets/          # Logos and design artifacts
├── backend/             # Django REST Framework backend
└── frontend/            # Next.js frontend application
```

---

## Development & Git Conventions

- **Branching**: For every phase, branch off `main` using the format `phase-N-short-slug` (e.g., `phase-1-backend-auth`).
- **Commit Messages**: Strictly follow **Conventional Commits v1.0.0**:
  `<type>(<optional scope>): <short description>`
  Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
- **Pull Requests**: Every phase concludes with a structured PR title and description outlining changes, architectural rationale, and verification steps.
