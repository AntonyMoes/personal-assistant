# Personal LLM Assistant — Architecture

## Overview

- **Frontend**: React SPA (chats, memories, settings, in-chat permissions).
- **Backend**: Async Python over **raw aiohttp** (HTTP + WebSockets).
- **Models**: Swappable providers (OpenAI first, local later).
- **Tools & RAG**: Pluggable tools with **preview-before-execute** and capability-based permissions.
- **Storage**: Pluggable backends; start with file-based (chats, memories, embeddings); migration path between backends.

---

## 1. React Web UI

- **Streaming**: **WebSockets** (not SSE). Single WS connection per active chat (or one multiplexed) for real-time token/reasoning stream.
- **Chats**: List (sort by user, archived/active), archive/unarchive, switch model per chat, view linked memories.
- **Memories**: Global view of stored memories (filter, edit, delete).
- **Settings**: Default model, permissions defaults (always ask / ask once per chat / allow / deny per capability).
- **Permissions UX**: **In-chat, blocking**. When a tool requires permission:
  - The model first sends a **preview** of the proposed action (see Tools section).
  - Permission UI appears **inside the chat** (e.g. inline card or message).
  - Only that chat is blocked until the user approves or denies; no global modal.
  - After resolution, stream continues (tool runs or is skipped).

---

## 2. Async HTTP API (Backend)

- **Stack**: **Raw aiohttp** (no FastAPI/Starlette). Use `aiohttp.web` for HTTP routes and `aiohttp.web.WebSocketResponse` for WS.
- **Responsibilities**:
  - REST for CRUD: chats, memories, models list, settings.
  - **WebSocket** per chat (or multiplexed) for: message send + streaming back (tokens, reasoning, tool previews, permission requests, tool results).
- **User model**: Backend may support multiple users in data model (e.g. `user_id` on chats/memories), but **no auth code or UI**. A single **default/implied user** is used until you add multi-user support; no login, no tokens, no user switcher.

### Backend structure (Python 3.13+, aiohttp)

- **Config**: `config.yaml` (see `config.example.yaml`) + `backend/config.py` — config is loaded into dataclasses (`Config`, `ServerConfig`, `AppConfig`, `StorageConfig`, `ModelConfig`, `PermissionsConfig`). Server host/port, default user, storage paths, model provider name, permission defaults. Secrets via environment variables (e.g. `${OPENAI_API_KEY}`). Dependencies: `requirements.txt` (aiohttp, pyyaml).
- **Entry**: `backend/main.py` — `create_app()`, `run_app()`; loads config and mounts routes.
- **Routes**: `backend/routes/http.py` (REST: `/health`, `/chats`, `/memories`, `/models`, `/settings`), `backend/routes/ws.py` (WebSocket: `/ws/chats/{chat_id}`).
- **Interfaces** (swappable implementations):
  - `backend/interfaces/model.py` — `ModelProvider` (stream_chat, embed, list_models), `ChatRequest`, `ChatMessage`, `ModelEvent` / `ModelEventType`.
  - `backend/interfaces/storage.py` — `ChatStore`, `MemoryStore`, `EmbeddingStore`; `ChatRecord`, `MemoryRecord`.
  - `backend/interfaces/tools.py` — `Tool` (name, description, args_schema, capabilities, preview, call), `ToolPreview`, `ToolResult`, `ToolContext`, `Capability`.
- **Run**: from repo root, `pip install -r requirements.txt` then `python -m backend.main`. Config path: `config.yaml` in repo root, or pass to `run_app(config_path=...)`.

---

## 3. Swappable Model Interfaces

- **ModelProvider** interface (e.g. `stream_chat`, `embed`) with implementations: OpenAI, later local (Ollama / LM Studio / vLLM).
- **Exposed thoughts**: Stream **raw chain-of-thought** (and any other reasoning) to the client over WebSocket so the UI can show full reasoning, not only high-level summaries.

### Model switch per chat

- The **model used for a chat** is stored per chat (e.g. `ChatRecord.model`) and can be changed by the user.
- **When**: Model switch is allowed **only when there is no active request or token streaming** for that chat. While the backend is streaming a response for a chat, changing that chat’s model is disallowed (API returns an error or the UI disables the control).
- Backend must track whether each chat has an active stream; allow `PATCH /chats/{id}` (model change) only when the chat is idle.

### Interrupt streaming

- The user must be able to **stop the current generation** mid-stream (“cancel” / “interrupt”).
- **Flow**: Client sends an interrupt message over the WebSocket (e.g. `{ type: "interrupt" }`). Backend stops consuming the model stream (e.g. cancel the async task or close the provider stream), sends a terminal event to the client (e.g. `done` with `stopped: true`), and persists whatever was generated so far as the assistant message.
- **ModelProvider**: Streaming should be cancellable (e.g. `stream_chat` is an async generator that can be closed from outside, or the provider accepts an abort signal). Implementations (OpenAI, local) must support early termination where the underlying API allows it.

---

## 4. Tools, RAGs, and Special Actions

- **Tool interface**: name, description, JSON schema for args, `async call(args, context) -> ToolResult`.
- **Capabilities**: Each tool declares capabilities (e.g. `filesystem_write`, `web_search`, `obsidian_modify`). Permissions are configured per capability (always ask / ask once per chat / allow / deny).
- **Preview-before-execute**:
  - When the model decides to use a tool, it does **not** execute immediately.
  - Backend asks the **ModelProvider** (or a dedicated step) to produce a **preview** of the proposed action: human-readable summary of what will be done (e.g. “Create file `foo.md` with content …”, “Run web search for …”).
  - This preview is sent to the client over the WebSocket.
  - **If permission is “always allow”**: optionally skip UI and run after preview (or still show preview in chat for transparency).
  - **If permission is “ask”**: show the preview in-chat and block until user approves/denies.
  - Only after approval (or auto-allow) does the backend actually call the tool and stream the result.
- **RAG**: Implemented as tools (e.g. Obsidian search, file search) using the shared embedding + vector storage; same preview/permission flow if the tool is considered sensitive.

---

## 5. Storage Layer

- **Interfaces**: `ChatStore`, `MemoryStore`, `EmbeddingStore` (with implementations swappable).
- **Initial**: File-based (e.g. one file per chat, one per memory, file-based embeddings index).
- **Migration**: Utility to read from one backend and write to another (e.g. file → SQLite/Postgres, file embeddings → vector DB) without changing orchestration code.

---

## 6. Refinements Summary

| Area | Decision |
|------|----------|
| Streaming | WebSockets only (no SSE). |
| Permission UI | In-chat, blocks only current chat until resolved. |
| Backend | Raw aiohttp (HTTP + WebSocket). |
| Tool execution | Preview of proposed action first, then permission check, then execute or skip. |
| Users & auth | No auth code or UI; default single user implied until multi-user is added. |
| Reasoning | Exposed thoughts including raw chain-of-thought streamed to the UI. |
| Model switch | Allowed per chat only when no active request or streaming; rejected while stream is active. |
| Interrupt | Client can send interrupt over WebSocket; backend stops stream, sends done(stopped), persists partial response. |

---

## 7. LLM API optimizations

A separate list is kept in **`docs/optimizations.md`**: which optimizations are implementable now (RAG, tool-first) and what is needed for the rest (multi-model routing, prompt caching, local-for-cheap-tasks, batch). That doc is the single place to track status and required work.
