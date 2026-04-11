# Agent Wiki

A personal knowledge management system powered by LLM. Transform documents into interconnected wiki pages automatically.

> **Status:** In active development

## Features

### Document Processing
- **Multi-format support** - PDF, DOCX, PPTX, Excel, CSV, Markdown
- **Image extraction** - OCR via Vertex AI Gemini Vision
- **Scanned PDF support** - Automatic fallback to vision model

### Wiki Generation
- **Two-step ingest** - Analysis → Generation pipeline
- **Entity/concept extraction** - Automatic identification of key elements
- **Wikilinks** - `[[cross-references]]` between pages
- **YAML frontmatter** - Structured metadata on every page

### Karpathy Architecture
Based on [Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f):
- **index.md** - Auto-generated content catalog
- **log.md** - Operation history
- **Obsidian export** - Download as compatible vault

### Knowledge Graph
- Visualize connections between pages
- Community detection
- Gap analysis

## Tech Stack

**Backend:**
- FastAPI + SQLAlchemy + PostgreSQL
- Vertex AI Gemini (multimodal)
- Alembic migrations

**Frontend:**
- React + TypeScript + Vite
- TailwindCSS + shadcn/ui
- React Router

## Quick Start

```bash
# Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
npm install
npm run dev
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /projects/:id/sources/upload` | Upload document |
| `POST /projects/:id/sources/:id/extract` | Extract text (LLM for images) |
| `POST /projects/:id/ingest` | Generate wiki pages |
| `GET /projects/:id/wiki/index` | Get index.md |
| `GET /projects/:id/wiki/log` | Get log.md |
| `GET /projects/:id/export` | Download Obsidian vault |

## Architecture

```
Sources (PDF, images, etc.)
    ↓
Extraction (pdfminer / Gemini Vision)
    ↓
LLM Analysis & Generation
    ↓
Wiki Pages (Markdown + YAML frontmatter)
    ↓
Knowledge Graph + Export
```

## License

MIT
