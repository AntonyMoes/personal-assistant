import { API_BASE } from '../config';

export async function listMemories(params = {}) {
  const q = new URLSearchParams();
  if (params.limit != null) q.set('limit', params.limit);
  if (params.offset != null) q.set('offset', params.offset);
  if (params.chat_id != null) q.set('chat_id', params.chat_id);
  const url = `${API_BASE}/memories${q.toString() ? '?' + q : ''}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getMemory(memoryId) {
  const res = await fetch(`${API_BASE}/memories/${memoryId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function createMemory(body) {
  const res = await fetch(`${API_BASE}/memories`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function updateMemory(memoryId, body) {
  const res = await fetch(`${API_BASE}/memories/${memoryId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function deleteMemory(memoryId) {
  const res = await fetch(`${API_BASE}/memories/${memoryId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(await res.text());
}
