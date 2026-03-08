import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { listChats, createChat, updateChat, deleteChat } from '../api/chats';
import ConfirmModal from '../components/ConfirmModal';

export default function ChatListPage() {
  const navigate = useNavigate();
  const [chats, setChats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [renamingId, setRenamingId] = useState(null);
  const [renameValue, setRenameValue] = useState('');
  const [deleteConfirmChatId, setDeleteConfirmChatId] = useState(null);

  const loadChats = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listChats({ sort: 'updated_at', order: 'desc' });
      setChats(data.chats || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadChats();
  }, []);

  const handleCreate = async () => {
    setError(null);
    try {
      const chat = await createChat({ title: 'New chat' });
      setChats((prev) => [chat, ...prev]);
      navigate(`/chat/${chat.id}`);
    } catch (e) {
      setError(e.message);
    }
  };

  const handleRenameStart = (chat) => {
    setRenamingId(chat.id);
    setRenameValue(chat.title || '');
  };

  const handleRenameSubmit = async (e) => {
    e.preventDefault();
    if (!renamingId) return;
    setError(null);
    try {
      const updated = await updateChat(renamingId, { title: renameValue.trim() || 'New chat' });
      setChats((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      setRenamingId(null);
    } catch (e) {
      setError(e.message);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteConfirmChatId) return;
    setError(null);
    try {
      await deleteChat(deleteConfirmChatId);
      setChats((prev) => prev.filter((c) => c.id !== deleteConfirmChatId));
      setDeleteConfirmChatId(null);
    } catch (e) {
      setError(e.message);
    }
  };

  if (loading) return <div className="page-message">Loading chats…</div>;
  if (error) return <div className="page-message error">Error: {error}</div>;

  return (
    <div className="chat-list-page">
      <div className="page-header">
        <h1>Chats</h1>
        <button type="button" className="btn btn-primary" onClick={handleCreate}>
          New chat
        </button>
      </div>
      <ul className="chat-list">
        {chats.length === 0 ? (
          <li className="chat-list-empty">No chats yet. Create one to get started.</li>
        ) : (
          chats.map((chat) => (
            <li key={chat.id} className="chat-list-item">
              {renamingId === chat.id ? (
                <form onSubmit={handleRenameSubmit} className="chat-rename-form">
                  <input
                    type="text"
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onBlur={handleRenameSubmit}
                    onKeyDown={(e) => e.key === 'Escape' && setRenamingId(null)}
                    autoFocus
                    className="chat-rename-input"
                  />
                </form>
              ) : (
                <>
                  <button
                    type="button"
                    className="chat-list-link"
                    onClick={() => navigate(`/chat/${chat.id}`)}
                  >
                    {chat.title || 'New chat'}
                  </button>
                  <button
                    type="button"
                    className="chat-list-rename"
                    onClick={() => handleRenameStart(chat)}
                    aria-label="Rename"
                  >
                    ✎
                  </button>
                  <button
                    type="button"
                    className="chat-list-delete"
                    onClick={() => setDeleteConfirmChatId(chat.id)}
                    aria-label="Delete chat"
                  >
                    🗑
                  </button>
                </>
              )}
            </li>
          ))
        )}
      </ul>
      {deleteConfirmChatId && (
        <ConfirmModal
          title="Delete chat?"
          message="This cannot be undone."
          confirmLabel="Delete"
          cancelLabel="Cancel"
          danger
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeleteConfirmChatId(null)}
        />
      )}
    </div>
  );
}
