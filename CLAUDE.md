# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Application

Always use `uv` to run Python commands and manage dependencies — never `pip` directly. Add packages with `uv add <package>`, not `pip install`.

```bash
# Install dependencies (first time)
uv sync

# Start the server (from repo root)
./run.sh

# Or manually
cd backend && uv run uvicorn app:app --reload --port 8000
```

Requires a `.env` file in the repo root with `ANTHROPIC_API_KEY=...` (copy from `.env.example`).

The server starts at `http://localhost:8000`. On startup it auto-loads all `.txt` files from `docs/` into ChromaDB.

## Architecture

The backend is a FastAPI app (`backend/app.py`) that serves both the REST API and the static frontend from `frontend/`. All backend modules are in `backend/` and imports are relative to that directory (no package prefix).

**RAG pipeline:**
- `RAGSystem` (`rag_system.py`) is the central orchestrator instantiated once at startup.
- `DocumentProcessor` parses course `.txt` files into `Course`/`Lesson`/`CourseChunk` Pydantic models, then splits lesson content into sentence-based overlapping chunks.
- `VectorStore` wraps ChromaDB with two collections: `course_catalog` (one doc per course for semantic name resolution) and `course_content` (all text chunks). Embeddings use `all-MiniLM-L6-v2` via `sentence-transformers`, running locally.
- `AIGenerator` handles Anthropic API calls. Queries go through a two-call loop: first call includes the `search_course_content` tool; if Claude calls it, tool results are fed back and a second call produces the final answer.
- `CourseSearchTool` / `ToolManager` (`search_tools.py`) define the tool Claude can call. `ToolManager` is extensible — register additional `Tool` subclasses to expose more tools to the model.
- `SessionManager` holds in-memory conversation history (last 2 exchanges by default), keyed by session ID. Sessions are created server-side and returned to the frontend on first query.

**Query flow:** `POST /api/query` → `RAGSystem.query()` → `AIGenerator` (1st Claude call) → optional `VectorStore.search()` → `AIGenerator` (2nd Claude call) → return answer + sources.

## Course Document Format

Files in `docs/` must follow this structure for the parser to work correctly:

```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>
Lesson 0: <title>
Lesson Link: <url>
<content...>
Lesson 1: <title>
...
```

The course title doubles as the unique ID in ChromaDB — duplicate titles are skipped on reload.

## Key Config Values (`backend/config.py`)

| Setting | Default | Effect |
|---|---|---|
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Model used for generation |
| `CHUNK_SIZE` | 800 chars | Max chunk size for vector storage |
| `CHUNK_OVERLAP` | 100 chars | Sentence overlap between chunks |
| `MAX_RESULTS` | 5 | Max chunks returned per search |
| `MAX_HISTORY` | 2 | Conversation exchanges kept per session |
| `CHROMA_PATH` | `./chroma_db` | ChromaDB persistence directory (relative to `backend/`) |
