# Todo (implementation order)

- [x] Define `ModelProvider` and event types for streaming (token, reasoning, tool_call, tool_preview, etc.) — in `backend/interfaces/model.py`.
- [x] Define tool preview format (e.g. title, summary, affected resources, dry-run result) — in `backend/interfaces/tools.py` (`ToolPreview`, `Tool.preview()`).
- [x] Implement aiohttp app skeleton: routes + one WS endpoint per chat — `backend/main.py`, `backend/routes/http.py`, `backend/routes/ws.py`.
- [ ] Define WebSocket message schema (client → server: send message, permission decision; server → client: token, reasoning, tool preview, permission request, tool result, done) — document and implement in `backend/routes/ws.py`.
- [ ] Implement file-based storage: `ChatStore`, `MemoryStore`, `EmbeddingStore` (see `backend/interfaces/storage.py`).
- [ ] Implement OpenAI `ModelProvider` and wire config + stores into app.
- [ ] Implement chat orchestration: load chat + memories, stream via model, handle tool preview → permission → execute, persist messages.
- [ ] Enforce model switch per chat only when idle: track active stream per chat; reject PATCH /chats/{id} (model change) while streaming (see architecture §3).
- [ ] Implement interrupt streaming: WebSocket interrupt message from client; backend cancels model stream, sends done(stopped), persists partial assistant message (see architecture §3).
- [ ] Add tests for all backend components (config, interfaces, routes, storage implementations, model provider, orchestration).
