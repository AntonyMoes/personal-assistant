import { API_BASE } from '../config';

export async function getSettings() {
  const res = await fetch(`${API_BASE}/settings`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function updateSettings(body) {
  const res = await fetch(`${API_BASE}/settings`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
