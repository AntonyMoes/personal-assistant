# Todo (implementation order)

- [x] Define `ModelProvider` and event types for streaming (token, reasoning, tool_call, tool_preview, etc.) — in `backend/interfaces/model.py`.
- [x] Define tool preview format (e.g. title, summary, affected resources, dry-run result) — in `backend/interfaces/tools.py` (`ToolPreview`, `Tool.preview()`).
- [x] Implement aiohttp app skeleton: routes + one WS endpoint per chat — `backend/main.py`, `backend/routes/http.py`, `backend/routes/ws.py`.
- [ ] Define WebSocket message schema (client → server: send message, permission decision; server → client: token, reasoning, tool preview, permission request, tool result, done) — document and implement in `backend/routes/ws.py`.
- [ ] Implement file-based storage: `ChatStore`, `MemoryStore`, `EmbeddingStore` (see `backend/interfaces/storage.py`).
- [ ] Implement OpenAI `ModelProvider` and wire config + stores into app.
- [ ] Implement chat orchestration: load chat + memories, stream via model, handle tool preview → permission → execute, persist messages.
