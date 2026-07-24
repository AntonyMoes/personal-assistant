# Agent guide — personal-assistant

Jarvis: a personal LLM assistant (aiohttp backend + React SPA) with tool calling, global memories, and Obsidian access. Custom orchestration — no LangChain.

## Run

From repo root (venv activated or use `.venv/Scripts/python` on Windows):

```bash
# Config (first time)
cp config.example.yaml config.yaml
# Optional: copy .env.example → .env and set OPENAI_API_KEY

pip install -r requirements.txt
python -m backend.main          # http://127.0.0.1:8765

cd frontend && npm install && npm start   # http://localhost:1234
```

Do **not** run `python backend/main.py` — import the package from the repo root.

Tests: `python -m pytest` (or `.venv/Scripts/python -m pytest`).

## Config & secrets

| Item | Notes |
|------|--------|
| `config.yaml` | Local; gitignored. Copy from `config.example.yaml`. |
| `.env` | Optional; gitignored. See `.env.example`. |
| `OPENAI_API_KEY` | Required for `model.provider: openai`. |
| `OBSIDIAN_VAULT_PATH` | **Host** vault path for Docker Compose volume mount only (`→ /vault` in container). App path is `app.obsidian_vault_path` in config (`/vault` in Docker; host path for local). |
| `storage.backend` | Prefer `file` so chats/memories persist under `data/`. Use `memory` only for ephemeral/dev. |

`${VAR}` in YAML is substituted from the environment.

## Architecture (where to look)

| Area | Path |
|------|------|
| App wiring / DI | `backend/main.py` |
| Chat + tool loop | `backend/orchestration.py` |
| System prompt | `prompts/system.md` (injected every turn) |
| Model providers | `backend/providers/` |
| Stores | `backend/storage/` (`ChatStore`, `MemoryStore`, `EmbeddingStore`) |
| Tools | `backend/tools/` (`remember`, `forget`, `obsidian`) |
| HTTP / WS | `backend/routes/` |
| Design notes | `docs/architecture.md`, `docs/ws_schema.md` |

Interfaces live in `backend/interfaces/`. Prefer extending protocols + factories over hard-coding providers.

## Conventions

- Keep changes scoped; match existing style (async aiohttp, dataclasses, protocols).
- Do not commit `config.yaml`, `.env`, or `data/`.
- Acceptance bar: existing pytest suite should pass; add tests for new behavior.
- Frontend: Parcel React SPA under `frontend/`; API defaults to `http://127.0.0.1:8765`.

## Known scaffolding (do not “fix” by deleting)

- **`EmbeddingStore`**: created and passed into `ToolContext`, but **no tool uses it yet**. Always in-memory (even when `storage.backend: file`). Intended for future RAG / semantic memory — see `docs/optimizations.md` and `docs/todo.md`.
- **Prompt caching, history truncation, relevance-filtered memories**: planned; current orchestration dumps up to 50 memories and full chat history each turn.
