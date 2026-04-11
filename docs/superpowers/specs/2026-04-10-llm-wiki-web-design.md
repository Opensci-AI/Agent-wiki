# LLM Wiki — Web Application Design Spec

**Date:** 2026-04-10
**Status:** Approved
**Scope:** Convert LLM Wiki from Tauri desktop app to web app with FastAPI backend

## Decisions

| Decision | Choice |
|---|---|
| Backend | FastAPI, separated from frontend |
| Architecture | Hybrid — server handles auth, CRUD, LLM proxy, ingest, research; client handles UI |
| Auth | Email/password + OAuth (Google, GitHub), JWT |
| Database | PostgreSQL |
| File storage | Local filesystem + abstraction layer (S3 later) |
| Document extraction | OpenRouter (LLM multimodal) for PDF/images; Python libs for structured formats |
| Real-time | Server-Sent Events (SSE) |
| Deployment | Docker Compose (self-host), local dev first |
| LLM keys | Admin default + user override |
| Scope | All features in one pass |

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────┐
│                  Docker Compose                  │
│                                                  │
│  ┌──────────┐   ┌──────────────┐  ┌──────────┐  │
│  │  Nginx   │   │   FastAPI    │  │ PostgreSQL│  │
│  │ (proxy)  │──▶│   Backend    │──▶│    DB     │  │
│  │ :80/:443 │   │   :8000      │  │  :5432    │  │
│  └──────────┘   └──────────────┘  └──────────┘  │
│       │          │           │                   │
│       │          │           ▼                   │
│       │          │     ┌──────────┐              │
│       │          │     │  Local   │              │
│       │          │     │ Storage  │              │
│       │          │     │ /data/   │              │
│       │          │     └──────────┘              │
│       ▼          │                               │
│  ┌──────────┐   │  SSE                           │
│  │  React   │◀──┘                                │
│  │  SPA     │                                    │
│  │ (static) │                                    │
│  └──────────┘                                    │
└─────────────────────────────────────────────────┘
```

- **Nginx** serves React SPA (static) + reverse proxies `/api/*` to FastAPI
- **FastAPI** handles auth, CRUD, file upload, ingest orchestration, LLM proxy, SSE
- **PostgreSQL** stores users, projects, pages, sources, conversations, reviews, configs
- **Local Storage** (`/data/`) stores uploaded files — abstraction layer for S3 migration
- **LLM calls** go through backend to protect API keys

### Local Development (no Docker)

```bash
# PostgreSQL via container
docker run -d --name llm-wiki-db \
  -e POSTGRES_USER=wiki -e POSTGRES_PASSWORD=wiki -e POSTGRES_DB=llm_wiki \
  -p 5432:5432 postgres:16-alpine

# Backend: uvicorn --reload on :8000
# Frontend: Vite dev server on :5173, proxy /api → :8000
```

---

## 2. Database Schema

```sql
-- Auth & Users
users (
  id UUID PK,
  email VARCHAR UNIQUE,
  password_hash VARCHAR NULLABLE,        -- null for OAuth-only users
  display_name VARCHAR,
  oauth_provider VARCHAR NULLABLE,       -- google, github
  oauth_id VARCHAR NULLABLE,
  is_admin BOOLEAN DEFAULT false,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  deleted_at TIMESTAMP NULLABLE          -- soft delete
)

-- Config (admin defaults + user overrides)
system_config (
  key VARCHAR PK,                        -- 'llm_config', 'search_config'
  value JSONB
)
-- llm_config JSONB schema:
-- {
--   "provider": "openrouter|openai|anthropic|google|ollama|custom",
--   "apiKey": "...",
--   "model": "...",
--   "baseUrl": "..." (optional, for ollama/custom),
--   "maxContextSize": 128000 (optional)
-- }

user_config (
  user_id UUID FK → users,
  key VARCHAR,
  value JSONB,
  PK (user_id, key)
)

-- Projects & Content
projects (
  id UUID PK,
  owner_id UUID FK → users,
  name VARCHAR,
  purpose TEXT,                          -- was purpose.md
  schema TEXT,                           -- was schema.md
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  deleted_at TIMESTAMP NULLABLE          -- soft delete
)

pages (
  id UUID PK,
  project_id UUID FK → projects,
  path VARCHAR,                          -- 'entities/machine-learning.md'
  type VARCHAR,                          -- entity, concept, source, query, comparison, synthesis
  title VARCHAR,
  content TEXT,
  frontmatter JSONB,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  UNIQUE (project_id, path)
)

sources (
  id UUID PK,
  project_id UUID FK → projects,
  filename VARCHAR,
  original_name VARCHAR,
  content_type VARCHAR,                  -- pdf, docx, txt, md, clip, pptx, xlsx
  extracted_text TEXT NULLABLE,
  file_size BIGINT,
  storage_path VARCHAR,                  -- local path or S3 key
  status VARCHAR,                        -- uploaded, extracting, ready, failed
  created_at TIMESTAMP,
  UNIQUE (project_id, filename)
)

-- Chat
conversations (
  id UUID PK,
  project_id UUID FK → projects,
  user_id UUID FK → users,
  title VARCHAR,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)

messages (
  id UUID PK,
  conversation_id UUID FK → conversations,
  role VARCHAR,                          -- user, assistant, system
  content TEXT,
  created_at TIMESTAMP
)

-- Review
review_items (
  id UUID PK,
  project_id UUID FK → projects,
  source_id UUID FK → sources NULLABLE,
  type VARCHAR,                          -- contradiction, duplicate, missing-page, suggestion, confirm
  title VARCHAR,
  description TEXT,
  affected_pages TEXT[],
  search_queries TEXT[],
  options JSONB,
  resolved BOOLEAN DEFAULT false,
  created_at TIMESTAMP
)

-- Background Tasks
tasks (
  id UUID PK,
  project_id UUID FK → projects,
  user_id UUID FK → users,
  type VARCHAR,                          -- ingest, deep_research, extraction
  status VARCHAR,                        -- queued, running, completed, failed
  input JSONB,
  result JSONB NULLABLE,
  progress_pct INTEGER DEFAULT 0,        -- 0-100 progress
  error TEXT NULLABLE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  started_at TIMESTAMP NULLABLE,
  completed_at TIMESTAMP NULLABLE
)

-- Ingest Cache
ingest_cache (
  project_id UUID FK → projects,
  source_filename VARCHAR,
  content_hash VARCHAR,
  written_paths TEXT[],
  created_at TIMESTAMP,
  PK (project_id, source_filename)
)
```

---

## 3. API Endpoints

### Conventions

- **Error format:** `{"detail": "message", "code": "ERROR_CODE"}` (FastAPI HTTPException)
- **Pagination:** Cursor-based for messages (`?cursor=<id>&limit=50`), offset-based for other lists (`?offset=0&limit=50`)
- **Auth:** All endpoints except `/auth/*` require `Authorization: Bearer <JWT>` header
- **SSE auth:** SSE endpoints accept JWT via query param `?token=<JWT>` (EventSource cannot send headers)

```
BASE: /api/v1

── Auth ──────────────────────────────────────────
POST   /auth/register                 email + password → JWT pair
POST   /auth/login                    email + password → JWT pair
GET    /auth/oauth/{provider}         redirect to OAuth provider
GET    /auth/oauth/{provider}/callback   receive auth code → JWT pair
POST   /auth/refresh                  refresh token (httpOnly cookie) → new JWT pair
GET    /auth/me                       current user info

JWT: access token (15min expiry, in response body)
     refresh token (7d expiry, httpOnly cookie, rotated on use)

── Projects ──────────────────────────────────────
GET    /projects                      list user's own projects
POST   /projects                      create project (scaffolds default pages)
GET    /projects/:id                  project detail + stats (owner only)
PATCH  /projects/:id                  update name, purpose, schema (owner only)
DELETE /projects/:id                  soft delete (owner only)

── Pages (Wiki) ──────────────────────────────────
GET    /projects/:id/pages            list pages (?type=entity&offset=0&limit=50)
GET    /projects/:id/pages/:pageId    content + frontmatter
POST   /projects/:id/pages            create page
PUT    /projects/:id/pages/:pageId    update content
DELETE /projects/:id/pages/:pageId    hard delete
GET    /projects/:id/pages/by-path?path=...   lookup by virtual path
GET    /projects/:id/pages/related?source=... find related wiki pages

── Sources ───────────────────────────────────────
GET    /projects/:id/sources          list sources (?status=ready&offset=0&limit=50)
POST   /projects/:id/sources/upload   multipart file upload (max 50MB)
POST   /projects/:id/sources/clip     web clipper endpoint
GET    /projects/:id/sources/:sid     source detail + extracted text
DELETE /projects/:id/sources/:sid     hard delete (removes file from storage)
POST   /projects/:id/sources/:sid/extract   trigger text extraction → task_id

Accepted upload types: pdf, docx, pptx, xlsx, xls, ods, txt, md, csv, png, jpg, jpeg, webp
Max file size: 50MB

── Ingest ────────────────────────────────────────
POST   /projects/:id/ingest           start ingest (source_id) → task_id
GET    /projects/:id/ingest/:taskId   task status
POST   /projects/:id/ingest/:taskId/cancel   abort

── Chat ──────────────────────────────────────────
GET    /projects/:id/conversations           list conversations (?offset=0&limit=50)
POST   /projects/:id/conversations           create conversation
GET    /conversations/:convId/messages       messages (?cursor=<id>&limit=50, newest first)
POST   /conversations/:convId/messages       send message → triggers LLM via SSE
DELETE /conversations/:convId                hard delete

── Deep Research ─────────────────────────────────
POST   /projects/:id/research         start research (topic, queries) → task_id
GET    /projects/:id/research/:taskId  task status + partial results

── Review ────────────────────────────────────────
GET    /projects/:id/reviews          list review items (?resolved=false)
PATCH  /projects/:id/reviews/:rid     resolve / update

── Graph ─────────────────────────────────────────
GET    /projects/:id/graph            nodes + edges + communities
GET    /projects/:id/graph/insights   knowledge gaps + surprising connections

── Search ────────────────────────────────────────
GET    /projects/:id/search?q=term    full-text + graph-expanded search (max 20 results)

── Lint ──────────────────────────────────────────
GET    /projects/:id/lint             run lint checks

── Config ────────────────────────────────────────
GET    /config                        effective config (merged admin + user)
PUT    /config                        update user config (llm, search, language)
GET    /admin/config                  admin defaults (is_admin required)
PUT    /admin/config                  update admin defaults (is_admin required)

── SSE Streams (auth via ?token=<JWT>) ───────────
GET    /projects/:id/stream/ingest/:taskId     ingest progress + tokens
GET    /projects/:id/stream/chat/:convId       LLM chat streaming
GET    /projects/:id/stream/research/:taskId   research progress
GET    /projects/:id/stream/activity           all task updates for project
```

### Authorization Model

- Users can only access their own projects (`projects.owner_id = current_user.id`)
- All sub-resource endpoints (pages, sources, conversations, etc.) inherit project ownership check
- Admin endpoints (`/admin/config`) require `users.is_admin = true`
- First user created via `ADMIN_EMAIL` env var gets `is_admin = true`
- No project sharing in v1 — owner-only access

### Web Clipper Endpoint

`POST /projects/:id/sources/clip`

```json
// Request
{
  "title": "Article Title",
  "url": "https://example.com/article",
  "content": "Markdown content..."
}

// Response
{
  "id": "uuid",
  "filename": "article-title-20260410.md",
  "status": "ready"
}
```

Creates a source with `content_type: clip`, generates slug from title, stores as markdown with frontmatter (type, title, url, clipped date, origin: web-clip, tags: [web-clip]).

---

## 4. Backend Structure

```
backend/
├── app/
│   ├── main.py                    # FastAPI app, CORS, lifespan, startup recovery
│   ├── config.py                  # Settings from env vars
│   │
│   ├── api/                       # Route handlers
│   │   ├── deps.py                # get_db, get_current_user, require_project_owner
│   │   ├── auth.py
│   │   ├── projects.py
│   │   ├── pages.py
│   │   ├── sources.py
│   │   ├── ingest.py
│   │   ├── chat.py
│   │   ├── research.py
│   │   ├── reviews.py
│   │   ├── graph.py
│   │   ├── search.py
│   │   ├── lint.py
│   │   ├── config_routes.py
│   │   └── streams.py
│   │
│   ├── models/                    # SQLAlchemy ORM
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── page.py
│   │   ├── source.py
│   │   ├── conversation.py
│   │   ├── message.py
│   │   ├── review_item.py
│   │   ├── task.py
│   │   ├── config.py
│   │   └── ingest_cache.py
│   │
│   ├── schemas/                   # Pydantic models
│   │   ├── auth.py
│   │   ├── project.py
│   │   ├── page.py
│   │   ├── source.py
│   │   ├── chat.py
│   │   ├── review.py
│   │   ├── task.py
│   │   └── config.py
│   │
│   ├── services/                  # Business logic
│   │   ├── auth_service.py
│   │   ├── project_service.py
│   │   ├── page_service.py
│   │   ├── source_service.py      # Upload, clip, extraction dispatch
│   │   ├── extraction_service.py  # Document extraction (local libs + OpenRouter)
│   │   ├── ingest_service.py      # Port from ingest.ts
│   │   ├── chat_service.py
│   │   ├── research_service.py    # Port from deep-research.ts + optimize-research-topic.ts
│   │   ├── graph_service.py       # Port from wiki-graph.ts + graph-relevance.ts + graph-insights.ts
│   │   ├── search_service.py      # Port from search.ts
│   │   ├── lint_service.py        # Port from lint.ts
│   │   ├── review_service.py
│   │   ├── wikilink_service.py    # Port from enrich-wikilinks.ts
│   │   └── config_service.py
│   │
│   ├── core/
│   │   ├── llm_client.py          # Multi-provider LLM streaming
│   │   ├── web_search.py          # Tavily integration
│   │   ├── storage.py             # StorageBackend ABC → LocalStorage / S3Storage
│   │   ├── security.py            # JWT encode/decode, password hashing (bcrypt)
│   │   ├── sse.py                 # SSE event formatting
│   │   └── background.py          # asyncio task manager with registry
│   │
│   └── db/
│       ├── session.py             # Async SQLAlchemy session
│       └── migrations/            # Alembic (initial migration creates all tables)
│
├── alembic.ini
├── requirements.txt
├── Dockerfile
└── .env.example
```

### Key patterns

- **3-layer:** api (routes) → services (logic) → models (data)
- **Storage abstraction:** `StorageBackend` ABC with `LocalStorage` and `S3Storage` implementations
- **Config resolution:** `effective = {**system_defaults, **user_overrides}`
- **Authorization dependency:** `require_project_owner(project_id, current_user)` reused across all project sub-resource routes

### Document Extraction Strategy

| Format | Method | Notes |
|---|---|---|
| PDF (scanned/image) | OpenRouter multimodal | LLM vision for OCR |
| PDF (text-based) | `pdfminer.six` | Fast, free, local |
| DOCX | `python-docx` | Structured extraction |
| PPTX | `python-pptx` | Slide text extraction |
| XLSX/XLS/ODS | `openpyxl` / `calamine` via Python | Tabular extraction |
| Images | OpenRouter multimodal | Vision model describes content |
| TXT/MD/CSV | Direct read | No extraction needed |

`extraction_service.py` auto-detects format and routes to appropriate method.

### Background Task Lifecycle

- **Startup recovery:** On server start, query `tasks` table for `status = 'running'` → mark as `failed` with `error = 'server restarted'`
- **Concurrency limit:** Max 3 concurrent tasks per user (configurable)
- **Cleanup:** Completed/failed tasks retained for 30 days, then purged by periodic cleanup
- **Cancellation:** Tasks check `asyncio.Event` flag between steps; SSE stream closes on cancel

### CORS Configuration

- **Development:** Allow `http://localhost:5173` (Vite dev server)
- **Production:** Allow only the configured domain (from `CORS_ORIGINS` env var)

### Rate Limiting

- LLM proxy endpoints (chat, ingest, research): 10 requests/min per user
- Auth endpoints: 5 attempts/min per IP
- File upload: 20 uploads/min per user
- Implemented via `slowapi` middleware

---

## 5. Frontend Changes

### Replace transport layer

```
src/api/                           # NEW — replaces src/commands/fs.ts
├── client.ts                      # fetch wrapper, JWT interceptor, auto-refresh
├── auth.ts
├── projects.ts
├── pages.ts
├── sources.ts
├── chat.ts
├── ingest.ts
├── research.ts
├── reviews.ts
├── graph.ts
├── search.ts
├── lint.ts
├── config.ts
└── sse.ts                         # EventSource helpers (handles ?token= auth)
```

### Add auth pages

```
src/pages/
├── login.tsx
├── register.tsx
└── forgot-password.tsx
```

Auth context/provider wrapping `App.tsx`, redirect when unauthenticated.

### Zustand store changes (minimal)

- `wiki-store.ts`: Replace `path` with `projectId` (UUID)
- `chat-store.ts`: Remove `persist.ts` calls → API calls
- `review-store.ts`: Remove local JSON → API calls
- `research-store.ts`: Subscribe SSE instead of client-side queue
- `activity-store.ts`: Subscribe SSE `/stream/activity`

### Remove (moved to backend)

- `src/commands/fs.ts` → `src/api/*`
- `src/lib/project-store.ts` → API config
- `src/lib/persist.ts` → DB persistence
- `src/lib/ingest.ts` → `ingest_service.py`
- `src/lib/ingest-cache.ts` → DB ingest_cache table
- `src/lib/deep-research.ts` → `research_service.py`
- `src/lib/optimize-research-topic.ts` → `research_service.py`
- `src/lib/llm-client.ts` → `core/llm_client.py`
- `src/lib/web-search.ts` → `core/web_search.py`
- `src/lib/wiki-graph.ts` → `graph_service.py`
- `src/lib/graph-relevance.ts` → `graph_service.py`
- `src/lib/graph-insights.ts` → `graph_service.py`
- `src/lib/search.ts` → `search_service.py`
- `src/lib/lint.ts` → `lint_service.py`
- `src/lib/enrich-wikilinks.ts` → `wikilink_service.py`
- `src/lib/clip-watcher.ts` → backend clip endpoint
- `src/lib/auto-save.ts` → DB auto-persists

### Keep unchanged

- All `src/components/*` UI components
- `src/lib/latex-to-unicode.ts` — client-side math rendering
- `src/lib/templates.ts` — scenario templates (UI only)
- `src/lib/file-types.ts` — file type detection (used by upload UI)
- `src/lib/path-utils.ts` — path normalization (used by UI)
- `src/lib/utils.ts` — general utilities
- `src/i18n/` — internationalization

### Obsidian compatibility

Not supported in web version. Users who want Obsidian access can use a future "export project" feature to download wiki as a folder with `.obsidian` configs.

---

## 6. Docker Compose (Production)

```yaml
services:
  nginx:
    image: nginx:alpine
    ports: ["80:80"]
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
      - ./frontend/dist:/usr/share/nginx/html:ro  # built frontend
    depends_on: [backend]

  backend:
    build: ./backend
    expose: ["8000"]
    environment:
      - DATABASE_URL=postgresql+asyncpg://wiki:wiki@db:5432/llm_wiki
      - STORAGE_PATH=/data/uploads
      - JWT_SECRET=${JWT_SECRET}
      - CORS_ORIGINS=https://your-domain.com
      - ADMIN_EMAIL=${ADMIN_EMAIL}
      - ADMIN_PASSWORD=${ADMIN_PASSWORD}
      - DEFAULT_LLM_API_KEY=${DEFAULT_LLM_API_KEY}
      - OAUTH_GOOGLE_CLIENT_ID=${OAUTH_GOOGLE_CLIENT_ID}
      - OAUTH_GOOGLE_CLIENT_SECRET=${OAUTH_GOOGLE_CLIENT_SECRET}
    volumes: [upload_data:/data/uploads]
    depends_on:
      db: { condition: service_healthy }

  db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=wiki
      - POSTGRES_PASSWORD=wiki
      - POSTGRES_DB=llm_wiki
    volumes: [pg_data:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U wiki"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  pg_data:
  upload_data:
```

### Build & Deploy

```bash
# 1. Build frontend
cd frontend && pnpm build   # outputs to frontend/dist/

# 2. Launch stack
docker compose up -d --build

# First run: auto-creates admin user, runs Alembic migrations
```

### Nginx SSE config

```nginx
location /api/ {
    proxy_pass http://backend:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_buffering off;        # required for SSE
    proxy_cache off;
    proxy_read_timeout 3600s;   # long-lived SSE connections
}
```

### Backend Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY alembic.ini .
COPY alembic/ ./alembic/
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

---

## 7. Migration Mapping

### Tauri IPC → REST API

| Tauri IPC | REST Endpoint |
|---|---|
| `readFile({path})` | `GET /projects/:id/pages/:pageId` |
| `writeFile({path, contents})` | `PUT /projects/:id/pages/:pageId` |
| `listDirectory({path})` | `GET /projects/:id/pages?type=...` |
| `findRelatedWikiPages(...)` | `GET /projects/:id/pages/related?source=...` |
| `preprocessFile({path})` | `POST /projects/:id/sources/:sid/extract` |
| `createProject(...)` | `POST /projects` |
| `openProject(...)` | `GET /projects/:id` |
| `deleteFile({path})` | `DELETE /projects/:id/pages/:pageId` or `sources/:sid` |
| `copyFile(...)` | Not needed — DB handles |
| `createDirectory(...)` | Not needed — virtual paths in DB |
| Clip server `POST /clip` | `POST /projects/:id/sources/clip` |
| Tauri store (llmConfig) | `GET/PUT /config` |
| persist.ts (chat JSON) | DB conversations + messages tables |
| persist.ts (review JSON) | DB review_items table |

### Client-side → Server-side

| TypeScript module | Python service |
|---|---|
| `ingest.ts` | `ingest_service.py` |
| `ingest-cache.ts` | DB `ingest_cache` table |
| `deep-research.ts` | `research_service.py` |
| `optimize-research-topic.ts` | `research_service.py` |
| `llm-client.ts` | `core/llm_client.py` |
| `llm-providers.ts` | `core/llm_client.py` (provider configs) |
| `web-search.ts` | `core/web_search.py` |
| `wiki-graph.ts` | `graph_service.py` |
| `graph-relevance.ts` | `graph_service.py` |
| `graph-insights.ts` | `graph_service.py` |
| `search.ts` | `search_service.py` |
| `lint.ts` | `lint_service.py` |
| `enrich-wikilinks.ts` | `wikilink_service.py` |
| `persist.ts` | DB layer (no dedicated service) |
| `project-store.ts` | `config_service.py` |
| `clip-watcher.ts` | `source_service.py` (clip endpoint) |
| `auto-save.ts` | Not needed — DB persists immediately |
