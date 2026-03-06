# WebSocket message schema

Canonical spec for the chat WebSocket (`/ws/chats/{chat_id}`). Implementation: `backend/ws_schema.py`.

## Wire format

Every message is a JSON object:

```json
{ "type": "<message_type>", "payload": { ... } }
```

`payload` may be `{}` or omitted when there are no extra fields.

---

## Client → Server (incoming)

| type | payload | Description |
|------|--------|-------------|
| `send_message` | `{ "content": string }` | Send a new user message; server streams the assistant reply. |
| `permission_decision` | `{ "tool_call_id": string, "approved": boolean }` | Response to a `permission_request`. Unblocks the stream. `tool_call_id` must match the server’s `permission_request.payload.tool_call_id`. |
| `interrupt` | `{}` | Stop the current generation. Server sends `done` with `stopped: true` and persists the partial reply. |

---

## Server → Client (outgoing)

| type | payload | Description |
|------|--------|-------------|
| `token` | `{ "text": string }` | Content tokens (streamed). |
| `reasoning` | `{ "text": string }` | Raw chain-of-thought / thinking (streamed). |
| `tool_call` | `{ "tool_call_id": string, "name": string, "arguments": object }` | Model requested a tool. Backend-generated id for this invocation; same value is used in `tool_preview`/`permission_request` and `tool_result`. |
| `tool_preview` | `{ "tool_call_id", "name", "title", "summary", "affected_resources", "dry_run_result"?, "arguments" }` | Preview of the proposed tool action (always sent before execution). `tool_call_id` correlates with `tool_call` and `tool_result`. |
| `permission_request` | Same as `tool_preview` | Backend is waiting for a `permission_decision` with this `tool_call_id`. |
| `tool_result` | `{ "tool_call_id", "success", "content", "data"? }` | Result of executing a tool. `tool_call_id` correlates with the originating `tool_call`. |
| `metadata` | `{ ... }` | Optional server-supplied info (arbitrary payload). |
| `done` | `{ "stopped": boolean }` | Generation finished. `stopped: true` if the user sent `interrupt`. |
| `error` | `{ "message": string, "code": string? }` | Error; stream ends. |

---

## Flow

1. Client sends `send_message` with user content.
2. Server streams `token`, `reasoning`, and optionally `tool_call` → `tool_preview` / `permission_request`.
3. If permission is required, client shows the preview and sends `permission_decision` with the same `tool_call_id`.
4. Server may send `tool_result`, then continue streaming until `done`.
5. Client may send `interrupt` at any time; server stops and sends `done(stopped: true)`.
