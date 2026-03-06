# React Frontend — Architecture

This document describes the frontend’s role, technology choices, structure, and contract with the backend. It is intended to stay relevant as the app evolves. For a step-by-step implementation list, see `docs/frontend-todo.md`. For overall system architecture, see `docs/architecture.md`.

---

## 1. Role and scope

The frontend is a single-page React app that:

- **Chats**: Shows a list of chats (titles), supports create/rename/archive and opening a chat; user sends messages and sees streamed assistant replies (tokens, optional reasoning); can interrupt generation and switch model per chat when idle.
- **Memories**: Lists memories (with optional filter by chat), and supports create, edit, and delete.
- **Settings**: Shows and edits default model and permission defaults (when the backend exposes them).
- **In-chat permissions**: When the backend sends a tool `permission_request`, the UI shows the preview inside the chat and blocks until the user approves or denies; it then sends `permission_decision` so the stream can continue.

Streaming uses **WebSockets only** (no SSE). Permission UI is **in-chat and blocking** for that chat only, not a global modal (see main architecture §1).

---

## 2. Technology choices

Decisions are biased toward simplicity and minimal tooling so the frontend stays easy to run and change.

| Area | Choice | Rationale |
|------|--------|-----------|
| Build | Parcel | Zero config, single entry (HTML + JS), no extra build setup. |
| Language | JavaScript | Plain JS and `.jsx`; no type system or compile step for types. |
| Routing | React Router v6 | Standard SPA routing; supports nested routes (e.g. sidebar + chat). |
| State | React context + `useState` / `useReducer` | No external state library; sufficient for chat list, current chat, messages, and UI state. |
| API | `fetch` + configurable base URL | No SDK; one config (or env) for API origin. |
| WebSocket | Native `WebSocket` | Used from a hook or context; one connection per active chat, lifecycle tied to the chat view. |
| Styling | Plain CSS | No Tailwind or CSS-in-JS; one or a few stylesheets to keep dependencies and build minimal. |

These choices can be revisited if requirements grow (e.g. TypeScript, different bundler, or state library).

---

## 3. App structure

```
frontend/
  index.html              # Parcel entry
  src/
    index.jsx             # React root
    App.jsx               # Router, layout (sidebar + main area)
    config.js             # API base URL and WebSocket URL (env or default)
    api/                  # REST: chats, memories, models, settings
    ws/                   # WebSocket connection and message handling for chat stream
    components/           # Reusable UI (buttons, inputs, cards, etc.)
    pages/
      ChatListPage.jsx    # Sidebar: list chats, create, select, rename
      ChatPage.jsx        # Messages, input, stream, interrupt, model selector
      MemoriesPage.jsx    # List, create, edit, delete memories
      SettingsPage.jsx    # Default model, permissions (when backend supports)
```

- **api/** and **ws/** isolate backend communication so the rest of the app depends on simple functions/hooks, not raw URLs or protocols.
- **config.js** is the single place for the API and WebSocket base URLs (e.g. from env or a default like `http://127.0.0.1:8765` and `ws://127.0.0.1:8765`).

---

## 4. Data and behavior

- **Chat list**: Loaded via `GET /chats`; refreshed after create, rename, or archive. Current chat is driven by the URL (e.g. `/chat/:chatId`). List and current chat can live in React state or context.
- **Messages**: Rendered from local state. When the backend does not yet expose message history, messages are derived from the current session (user input + streamed assistant reply). When `GET /chats/:id/messages` (or equivalent) exists, the chat view can load history on open and append new turns from the stream.
- **Streaming**: On send, the client ensures a WebSocket connection to `ws://…/ws/chats/:chatId`, sends `send_message`, and handles incoming messages: `token` and `reasoning` are accumulated into the current assistant turn; `done` or `error` finalizes it. The UI can offer a control to show or hide reasoning.
- **Interrupt**: A “Stop” (or similar) action sends `interrupt` on the WebSocket; the backend stops the stream and sends `done(stopped: true)`.
- **Model switch**: The chat UI can show a model selector backed by `GET /models` and `PATCH /chats/:id` (body: `model`). The backend may reject model changes while a stream is active; the UI should disable or reflect that (e.g. disable selector while streaming).
- **Tool permissions**: When the server sends a `permission_request` (same payload shape as `tool_preview`), the UI shows an inline card in the chat with the preview (title, summary, etc.) and Approve/Deny. On action, it sends `permission_decision` with the same `tool_call_id` and `approved: true|false`.

---

## 5. Backend contract

The frontend relies on the following. Details are in `docs/ws_schema.md` and the backend route docs.

**REST**

- Chats: `GET /chats`, `GET /chats/:id`, `POST /chats`, `PATCH /chats/:id` (e.g. `title`, `model`, `archived`).
- Memories: `GET /memories`, `GET /memories/:id`, `POST /memories`, `PATCH /memories/:id`, `DELETE /memories/:id`.
- Models: `GET /models`.
- Settings: `GET /settings`, `PATCH /settings` (when implemented).

**WebSocket**

- Endpoint: `ws://host:port/ws/chats/:chatId`.
- Client → server: `send_message`, `permission_decision`, `interrupt` (see `docs/ws_schema.md` for payloads).
- Server → client: `token`, `reasoning`, `tool_call`, `tool_preview`, `permission_request`, `tool_result`, `metadata`, `done`, `error`.

CORS must allow the frontend origin when it is served from a different host/port than the backend.

---

## 6. Out of scope (for now)

- **Auth / login**: Backend uses a single default user; no login or user switcher in the UI.
- **File storage / embeddings UI**: Managed on the backend; no dedicated frontend for file or embedding management.
- **Mobile-first or native**: Responsive layout is in scope; mobile-specific or native apps are not.
