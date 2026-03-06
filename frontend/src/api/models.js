import { API_BASE } from '../config';

export async function listModels() {
  const res = await fetch(`${API_BASE}/models`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
