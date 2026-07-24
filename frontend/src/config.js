/**
 * API and WebSocket base URLs.
 * Prefer process.env (Parcel), else same host the page was loaded from (LAN-friendly),
 * else localhost for non-browser contexts.
 */
const BACKEND_PORT = 8765;

function defaultOrigins() {
  if (typeof window !== 'undefined' && window.location?.hostname) {
    const host = window.location.hostname;
    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return {
      api: `${window.location.protocol}//${host}:${BACKEND_PORT}`,
      ws: `${wsProto}//${host}:${BACKEND_PORT}`,
    };
  }
  return {
    api: `http://127.0.0.1:${BACKEND_PORT}`,
    ws: `ws://127.0.0.1:${BACKEND_PORT}`,
  };
}

const defaults = defaultOrigins();
const apiOrigin = (typeof process !== 'undefined' && process.env?.API_URL) || defaults.api;
const wsOrigin = (typeof process !== 'undefined' && process.env?.WS_URL) || defaults.ws;

export const API_BASE = apiOrigin.replace(/\/$/, '');
export const WS_BASE = wsOrigin.replace(/\/$/, '');
