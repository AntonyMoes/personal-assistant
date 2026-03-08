import { useState, useEffect } from 'react';
import { listMemories, updateMemory, deleteMemory } from '../api/memories';
import ConfirmModal from '../components/ConfirmModal';

export default function MemoriesPage() {
  const [memories, setMemories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editContent, setEditContent] = useState('');
  const [deleteConfirmId, setDeleteConfirmId] = useState(null);

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

  const handleEditStart = (memory) => {
    setEditingId(memory.id);
    setEditContent(memory.content || '');
  };

  const handleEditSubmit = async (e) => {
    e?.preventDefault?.();
    if (!editingId) return;
    setError(null);
    try {
      const updated = await updateMemory(editingId, { content: editContent.trim() });
      setMemories((prev) =>
        prev.map((m) => (String(m.id) === String(updated.id) ? { ...m, ...updated } : m))
      );
      setEditingId(null);
    } catch (e) {
      setError(e.message);
    }
  };

  const handleEditCancel = () => {
    setEditingId(null);
    setEditContent('');
  };

  const handleDeleteConfirm = async () => {
    if (!deleteConfirmId) return;
    setError(null);
    try {
      await deleteMemory(deleteConfirmId);
      setMemories((prev) => prev.filter((m) => m.id !== deleteConfirmId));
      setDeleteConfirmId(null);
    } catch (e) {
      setError(e.message);
    }
  };

  if (loading) return <div className="page-message">Loading memories…</div>;
  if (error) return <div className="page-message error">Error: {error}</div>;

  return (
    <div className="memories-page">
      <h1>Memories</h1>
      <ul className="memory-list">
        {memories.length === 0 ? (
          <li className="memory-list-empty">No memories yet.</li>
        ) : (
          memories.map((m) => (
            <li key={m.id} className="memory-list-item">
              {editingId === m.id ? (
                <form onSubmit={handleEditSubmit} className="memory-edit-form">
                  <span className="memory-list-key">{m.key}</span>
                  <textarea
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    onKeyDown={(e) => e.key === 'Escape' && handleEditCancel()}
                    className="memory-edit-content"
                    rows={2}
                    autoFocus
                  />
                  <div className="memory-edit-actions">
                    <button type="button" className="btn" onClick={handleEditCancel}>
                      Cancel
                    </button>
                    <button type="submit" className="btn btn-primary">
                      Save
                    </button>
                  </div>
                </form>
              ) : (
                <>
                  <span className="memory-list-key">{m.key}</span>
                  <span className="memory-list-content">{m.content || '\u00a0'}</span>
                  <button
                    type="button"
                    className="memory-list-edit"
                    onClick={() => handleEditStart(m)}
                    aria-label="Edit"
                  >
                    ✎
                  </button>
                  <button
                    type="button"
                    className="memory-list-delete"
                    onClick={() => setDeleteConfirmId(m.id)}
                    aria-label="Delete memory"
                  >
                    🗑
                  </button>
                </>
              )}
            </li>
          ))
        )}
      </ul>
      {deleteConfirmId && (
        <ConfirmModal
          title="Delete memory?"
          message="This cannot be undone."
          confirmLabel="Delete"
          cancelLabel="Cancel"
          danger
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeleteConfirmId(null)}
        />
      )}
    </div>
  );
}
