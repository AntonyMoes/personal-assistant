import { useState, useEffect } from 'react';
import { listMemories, createMemory, updateMemory, deleteMemory } from '../api/memories';

export default function MemoriesPage() {
  const [memories, setMemories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadMemories = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listMemories();
      setMemories(data.memories || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMemories();
  }, []);

  if (loading) return <div className="page-message">Loading memories…</div>;
  if (error) return <div className="page-message error">Error: {error}</div>;

  return (
    <div className="memories-page">
      <h1>Memories</h1>
      <p className="page-message">List, create, edit, delete — to be wired in next.</p>
      <ul className="memory-list">
        {memories.map((m) => (
          <li key={m.id}>
            <strong>{m.key}</strong>: {m.content}
          </li>
        ))}
      </ul>
    </div>
  );
}
