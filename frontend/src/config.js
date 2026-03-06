/**
 * API and WebSocket base URLs. Parcel exposes env via process.env in development.
 * Default: backend on 127.0.0.1:8765.
 */
const apiOrigin = (typeof process !== 'undefined' && process.env?.API_URL) || 'http://127.0.0.1:8765';
const wsOrigin = (typeof process !== 'undefined' && process.env?.WS_URL) || 'ws://127.0.0.1:8765';

export const API_BASE = apiOrigin.replace(/\/$/, '');
export const WS_BASE = wsOrigin.replace(/\/$/, '');
