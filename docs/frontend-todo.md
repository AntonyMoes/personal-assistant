# Frontend Todo (implementation order)

- [x] **Scaffold**: Parcel + React (JavaScript), React Router, layout (sidebar + main content), config for API/WS base URL (env or default).
- [x] **API client**: Fetch helpers for REST (`/chats`, `/memories`, `/models`, `/settings`).
- [x] **Chat list**: Page/sidebar — list chats (GET /chats), create chat (POST), select chat → navigate to `/chat/:chatId`, rename (PATCH title).
- [x] **Chat view + WebSocket**: Message list (user/assistant), input, Send; connect WS to `/ws/chats/:chatId` on mount; send `send_message`, handle `token`/`reasoning`/`done`/`error`; append streamed reply to UI.
- [x] **Interrupt + model**: Stop button sends `interrupt`; model selector in chat (PATCH /chats/:id model when idle; disabled while streaming).
- [ ] **Memories**: Page — list (GET /memories), create (POST), edit (PATCH), delete (DELETE). Memories are global. In chat, `memory_created` WS message shows “Memory saved” with Delete button.
- [ ] **Settings**: Page — GET/PATCH /settings (default model, permissions) when backend supports it; placeholder otherwise.
- [ ] **Tool permission UI**: When server sends `permission_request`, show inline card in chat (title, summary, etc.); Approve/Deny buttons send `permission_decision` with same `tool_call_id`.
- [ ] **Polish**: Reasoning visibility toggle, empty/loading/error states, basic responsive layout, CORS if needed.

## Subtasks (tick as done)

### Scaffold
- [x] Create `frontend/` with Parcel + React (JavaScript, .jsx).
- [x] Add React Router, single layout with sidebar + outlet.
- [x] Add config.js for API base URL and WS URL (env or default, e.g. `http://127.0.0.1:8765`).

### API client
- [x] Implement `api/chats.js` (list, get, create, update).
- [x] Implement `api/memories.js` (list, get, create, update, delete).
- [x] Implement `api/models.js` (list) and `api/settings.js` (get, update).

### Chat list
- [x] ChatListPage or sidebar: fetch and display chats.
- [x] Create chat button → POST → add to list and navigate to new chat.
- [x] Click chat → navigate to `/chat/:chatId`.
- [x] Rename chat (inline or modal) → PATCH title.

### Chat view + WebSocket
- [x] ChatPage: read `chatId` from route, load chat (GET /chats/:id) for title/model.
- [x] Message list: show user and assistant messages (from state; history TBD when backend has GET messages).
- [x] Input + Send: on submit, send `send_message` over WS.
- [x] WS hook/context: connect, send, subscribe to incoming messages; parse type/payload (plain JS).
- [x] Accumulate `token` (and optionally `reasoning`) into current assistant message; on `done`/`error`, finalize.

### Interrupt + model
- [x] Stop button visible while streaming; sends `interrupt`.
- [ ] Model selector (dropdown) from GET /models; PATCH /chats/:id with model when changed; disabled when streaming.

### Memories
- [ ] MemoriesPage: list memories (GET /memories; all memories are global).
- [ ] Create memory form (key, content).
- [ ] Edit memory (PATCH content); delete (DELETE). In chat: show `memory_created` as “Memory saved” card with Delete button.

### Settings
- [ ] SettingsPage: display settings; form for default model / permissions when API is ready.

### Tool permission UI
- [ ] When `permission_request` received, render inline card with preview and Approve/Deny.
- [ ] On Approve/Deny, send `permission_decision` with `tool_call_id` and `approved`.

### Polish
- [ ] Toggle to show/hide reasoning in chat.
- [ ] Empty states (no chats, no messages).
- [ ] Loading and error states for API and WS.
- [ ] Basic responsive layout; CORS configuration if needed.
