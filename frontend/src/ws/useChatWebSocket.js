import { useRef, useCallback, useEffect, useState } from 'react';
import { WS_BASE } from '../config';

export function useChatWebSocket(chatId, callbacks = {}) {
  const wsRef = useRef(null);
  const callbacksRef = useRef(callbacks);
  const [isStreaming, setIsStreaming] = useState(false);
  const [lastError, setLastError] = useState(null);
  const [connected, setConnected] = useState(false);

  callbacksRef.current = callbacks;

  const connect = useCallback(() => {
    if (!chatId) return () => {};
    setConnected(false);
    const url = `${WS_BASE}/ws/chats/${chatId}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => { wsRef.current = null; setConnected(false); };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        const { type, payload = {} } = msg;
        const c = callbacksRef.current;
        if (type === 'token' && c.onToken) c.onToken(payload.text || '');
        if (type === 'reasoning' && c.onReasoning) c.onReasoning(payload.text || '');
        if (type === 'memory_created' && c.onMemoryCreated) c.onMemoryCreated(payload || {});
        if (type === 'memory_updated' && c.onMemoryUpdated) c.onMemoryUpdated(payload || {});
        if (type === 'memory_deleted' && c.onMemoryDeleted) c.onMemoryDeleted(payload || {});
        if (type === 'done') {
          setIsStreaming(false);
          if (c.onDone) c.onDone();
        }
        if (type === 'error') {
          setIsStreaming(false);
          const err = payload.message || 'Unknown error';
          setLastError(err);
          if (c.onError) c.onError(err);
        }
        if (type === 'token' || type === 'reasoning') setIsStreaming(true);
      } catch (_) {}
    };

    ws.onerror = () => setLastError('WebSocket error');

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [chatId]);

  const send = useCallback((type, payload = {}) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, payload }));
    }
  }, []);

  const sendMessage = useCallback((content) => {
    setIsStreaming(true);
    setLastError(null);
    send('send_message', { content });
  }, [send]);

  const sendInterrupt = useCallback(() => send('interrupt', {}), [send]);

  useEffect(() => {
    return connect();
  }, [connect]);

  return {
    connect,
    sendMessage,
    sendInterrupt,
    connected,
    isStreaming,
    lastError,
  };
}
