# Chat WebSocket (Postman)

Postman’s collection format only supports HTTP. WebSocket requests cannot be imported as WebSocket; they always open as HTTP. Use the steps below to create a real WebSocket request in Postman.

## 1. Create a WebSocket request

- **New → WebSocket Request** (or **Ctrl+N** / **Cmd+N**).
- Do **not** import the HTTP collection for this.

## 2. Set the URL

```
ws://127.0.0.1:8765/ws/chats/YOUR_CHAT_ID
```

Replace `YOUR_CHAT_ID` with a chat id from the HTTP API (e.g. run **Create Chat** in the Personal Assistant API collection and copy the `id` from the response).  
If your server uses another host/port, change the URL (e.g. `ws://localhost:8765/...`).

## 3. Connect

Click **Connect**. The connection badge should show “Connected”.

## 4. Send messages (JSON)

Type or paste JSON in the message box and click **Send**.

**Send a user message (starts the stream):**
```json
{"type": "send_message", "payload": {"content": "Hello"}}
```

**Interrupt current generation:**
```json
{"type": "interrupt", "payload": {}}
```

**Reply to a permission request (use the `tool_call_id` from the server message):**
```json
{"type": "permission_decision", "payload": {"tool_call_id": "<id from server>", "approved": true}}
```

## 5. What the server sends

- **token** – streamed reply text  
- **reasoning** – chain-of-thought (if any)  
- **tool_call** / **tool_result** – when tools (e.g. remember) are used  
- **done** – end of the turn (`payload.stopped` is true if you sent **interrupt**)  
- **error** – e.g. invalid message or chat not found  

Run the backend with `python -m backend.main` (default: `127.0.0.1:8765`).
