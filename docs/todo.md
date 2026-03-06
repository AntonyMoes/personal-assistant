# Todo (implementation order)

- [ ] Define WebSocket message schema (client → server: send message, permission decision; server → client: token, reasoning, tool preview, permission request, tool result, done).
- [ ] Define `ModelProvider` and event types for streaming (token, reasoning, tool_call, tool_preview, etc.).
- [ ] Define tool preview format (e.g. title, summary, affected resources, dry-run result if applicable).
- [ ] Implement aiohttp app skeleton: routes + one WS endpoint per chat (or channel-based multiplexing).
