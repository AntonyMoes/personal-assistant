import { useState, useEffect, useLayoutEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getChat, getChatMessages, updateChat, deleteChat } from '../api/chats';
import ConfirmModal from '../components/ConfirmModal';
import { createMemory, deleteMemory, updateMemory } from '../api/memories';
import { useChatWebSocket } from '../ws/useChatWebSocket';

export default function ChatPage() {
  const { chatId } = useParams();
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const skipNextScrollToBottomRef = useRef(false);
  const didFocusInputForChatRef = useRef(null);
  const [chat, setChat] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleValue, setTitleValue] = useState('');
  const [focusInputAfterSend, setFocusInputAfterSend] = useState(false);
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const SCROLL_TO_BOTTOM_THRESHOLD = 100;
  const INPUT_MIN_HEIGHT = 44;
  const INPUT_MAX_HEIGHT = 200;

  const { sendMessage, sendInterrupt, isStreaming, lastError } = useChatWebSocket(chatId, {
    onToken: (text) => {
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.role === 'assistant' && last.streaming) {
          next[next.length - 1] = { ...last, content: last.content + text };
          return next;
        }
        next.push({ role: 'assistant', content: text, streaming: true });
        return next;
      });
    },
    onReasoning: (text) => {
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.role === 'assistant' && last.streaming) {
          next[next.length - 1] = { ...last, reasoning: (last.reasoning || '') + text };
          return next;
        }
        next.push({ role: 'assistant', content: '', reasoning: text, streaming: true });
        return next;
      });
    },
    onDone: () => {
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.streaming) next[next.length - 1] = { ...last, streaming: false };
        return next;
      });
    },
    onMemoryCreated: (payload) => {
      if (!payload || payload.id == null) return;
      setMessages((prev) => [
        ...prev,
        {
          type: 'memory_created',
          id: String(payload.id),
          key: payload.key != null ? String(payload.key) : '',
          content: payload.content != null ? String(payload.content) : '',
        },
      ]);
    },
    onMemoryUpdated: (payload) => {
      if (!payload || payload.id == null) return;
      setMessages((prev) => [
        ...prev,
        {
          type: 'memory_updated',
          _clientId: `updated-${Date.now()}-${Math.random()}`,
          id: String(payload.id),
          key: payload.key != null ? String(payload.key) : '',
          old_content: payload.old_content != null ? String(payload.old_content) : '',
          new_content: payload.new_content != null ? String(payload.new_content) : '',
        },
      ]);
    },
    onMemoryDeleted: (payload) => {
      if (!payload || payload.key == null) return;
      setMessages((prev) => [
        ...prev,
        {
          type: 'memory_deleted',
          _clientId: `deleted-${Date.now()}-${Math.random()}`,
          id: payload.id != null ? String(payload.id) : '',
          key: String(payload.key),
          content: payload.content != null ? String(payload.content) : '',
        },
      ]);
    },
    onError: (err) => setError(err),
  });

  useEffect(() => {
    if (!chatId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([getChat(chatId), getChatMessages(chatId)])
      .then(([c, { messages: msgs }]) => {
        if (!cancelled) {
          setChat(c);
          setMessages((msgs || []).map((m) => ({ role: m.role, content: m.content || '', streaming: false })));
        }
      })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [chatId]);

  useEffect(() => {
    if (lastError) setError(lastError);
  }, [lastError]);

  // Focus input when chat is first opened (and when chat loads)
  useEffect(() => {
    if (chat && !loading && chatId && didFocusInputForChatRef.current !== chatId) {
      didFocusInputForChatRef.current = chatId;
      inputRef.current?.focus();
    }
  }, [chat, loading, chatId]);

  useLayoutEffect(() => {
    if (focusInputAfterSend && !editingTitle) {
      inputRef.current?.focus();
      setFocusInputAfterSend(false);
    }
  }, [focusInputAfterSend, editingTitle]);

  // Auto-resize textarea to fit content (smooth grow/shrink with min/max)
  useLayoutEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    const h = Math.min(INPUT_MAX_HEIGHT, Math.max(INPUT_MIN_HEIGHT, el.scrollHeight));
    el.style.height = `${h}px`;
    el.style.overflowY = h >= INPUT_MAX_HEIGHT ? 'auto' : 'hidden';
  }, [input]);

  useLayoutEffect(() => {
    if (skipNextScrollToBottomRef.current) {
      skipNextScrollToBottomRef.current = false;
      return;
    }
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Show "scroll to bottom" when user has scrolled up
  useEffect(() => {
    const el = messagesContainerRef.current;
    if (!el) return;
    const onScroll = () => {
      const { scrollTop, clientHeight, scrollHeight } = el;
      const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
      setShowScrollToBottom(distanceFromBottom > SCROLL_TO_BOTTOM_THRESHOLD);
    };
    el.addEventListener('scroll', onScroll, { passive: true });
    onScroll(); // initial check
    return () => el.removeEventListener('scroll', onScroll);
  }, [messages.length]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    setShowScrollToBottom(false);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || isStreaming) return;
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setInput('');
    sendMessage(text);
    setFocusInputAfterSend(true);
  };

  const handleRenameStart = () => {
    setTitleValue(chat?.title || '');
    setEditingTitle(true);
  };

  function getMemoryKey(m) {
    if (!m || typeof m !== 'object') return null;
    if (m.type === 'memory_created' || m.type === 'memory_updated' || m.type === 'memory_deleted') return m.key ?? null;
    return null;
  }

  function isMostRecentForMemoryKey(msgIndex) {
    const key = getMemoryKey(messages[msgIndex]);
    if (key == null || key === '') return true;
    for (let j = msgIndex + 1; j < messages.length; j++) {
      if (getMemoryKey(messages[j]) === key) return false;
    }
    return true;
  }

  const handleDeleteMemory = async (memoryId) => {
    try {
      await deleteMemory(memoryId);
      skipNextScrollToBottomRef.current = true;
      setMessages((prev) => prev.filter((m) => m.type !== 'memory_created' || m.id !== memoryId));
    } catch (err) {
      setError(err.message);
    }
  };

  const handleRollbackUpdate = async (msg) => {
    if (!msg.id || msg.old_content == null) return;
    try {
      await updateMemory(msg.id, { content: msg.old_content });
      skipNextScrollToBottomRef.current = true;
      setMessages((prev) => prev.filter((m) => m._clientId !== msg._clientId));
    } catch (err) {
      setError(err.message);
    }
  };

  const handleRollbackDelete = async (msg) => {
    if (!msg.key) return;
    try {
      await createMemory({ key: msg.key, content: msg.content ?? '' });
      skipNextScrollToBottomRef.current = true;
      setMessages((prev) => prev.filter((m) => m._clientId !== msg._clientId));
    } catch (err) {
      setError(err.message);
    }
  };

  const handleRenameSubmit = async (e) => {
    e?.preventDefault?.();
    if (!chatId || !chat) return;
    const title = (titleValue || '').trim() || 'New chat';
    setEditingTitle(false);
    if (title === (chat.title || '')) return;
    setError(null);
    try {
      const updated = await updateChat(chatId, { title });
      setChat(updated);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!chatId) return;
    setError(null);
    try {
      await deleteChat(chatId);
      setShowDeleteConfirm(false);
      navigate('/chat', { replace: true });
    } catch (err) {
      setError(err.message);
    }
  };

  if (!chatId) {
    navigate('/chat', { replace: true });
    return null;
  }
  if (loading && !chat) return <div className="page-message">Loading chat…</div>;
  if (error && !chat) return <div className="page-message error">Error: {error}</div>;

  return (
    <div className="chat-page">
      <div className="chat-content">
      <div className="chat-header">
        {editingTitle ? (
          <form onSubmit={handleRenameSubmit} className="chat-title-form">
            <input
              type="text"
              value={titleValue}
              onChange={(e) => setTitleValue(e.target.value)}
              onBlur={handleRenameSubmit}
              onKeyDown={(e) => e.key === 'Escape' && setEditingTitle(false)}
              autoFocus
              className="chat-title-input"
            />
          </form>
        ) : (
          <h1 className="chat-title">
            {chat?.title || 'Chat'}
            <button
              type="button"
              className="chat-title-edit"
              onClick={handleRenameStart}
              aria-label="Rename chat"
            >
              ✎
            </button>
            <button
              type="button"
              className="chat-title-delete"
              onClick={() => setShowDeleteConfirm(true)}
              aria-label="Delete chat"
            >
              🗑
            </button>
          </h1>
        )}
        {isStreaming && (
          <button type="button" className="btn btn-small" onClick={sendInterrupt}>
            Stop
          </button>
        )}
      </div>
      <div ref={messagesContainerRef} className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">Send a message to start.</div>
        )}
        {messages.map((m, i) =>
          m.type === 'memory_created' ? (
            <div key={`memory-${m.id || i}`} className="message message-memory message-memory-created">
              <div className="memory-created-content">
                <span className="memory-created-label">Memory saved:</span>{' '}
                {m.key ? <><strong>{m.key}</strong> = </> : null}
                {m.content ?? ''}
              </div>
              <button
                type="button"
                className="btn btn-small memory-delete"
                onClick={() => handleDeleteMemory(m.id)}
                aria-label="Delete memory"
                disabled={!m.id || !isMostRecentForMemoryKey(i)}
                title={!isMostRecentForMemoryKey(i) ? 'Only the most recent change for this memory can be undone.' : undefined}
              >
                Delete
              </button>
            </div>
          ) : m.type === 'memory_updated' ? (
            <div key={m._clientId || i} className="message message-memory message-memory-updated">
              <div className="memory-created-content">
                <span className="memory-created-label">Memory updated:</span>{' '}
                {m.key ? <><strong>{m.key}</strong></> : null}
                <div className="memory-diff">
                  <span className="memory-old">{m.old_content || '\u00a0'}</span>
                  <span className="memory-arrow"> → </span>
                  <span className="memory-new">{m.new_content ?? ''}</span>
                </div>
              </div>
              <button
                type="button"
                className="btn btn-small memory-rollback"
                onClick={() => handleRollbackUpdate(m)}
                aria-label="Roll back"
                disabled={!isMostRecentForMemoryKey(i)}
                title={!isMostRecentForMemoryKey(i) ? 'Only the most recent change for this memory can be undone.' : undefined}
              >
                Roll back
              </button>
            </div>
          ) : m.type === 'memory_deleted' ? (
            <div key={m._clientId || i} className="message message-memory message-memory-deleted">
              <div className="memory-created-content">
                <span className="memory-created-label">Memory deleted:</span>{' '}
                {m.key ? <><strong>{m.key}</strong> = </> : null}
                {m.content ?? ''}
              </div>
              <button
                type="button"
                className="btn btn-small memory-rollback"
                onClick={() => handleRollbackDelete(m)}
                aria-label="Roll back"
                disabled={!isMostRecentForMemoryKey(i)}
                title={!isMostRecentForMemoryKey(i) ? 'Only the most recent change for this memory can be undone.' : undefined}
              >
                Roll back
              </button>
            </div>
          ) : (
            <div key={i} className={`message message-${m.role}`}>
              <div className="message-content">{m.content || '\u00a0'}</div>
              {m.reasoning && <div className="message-reasoning">{m.reasoning}</div>}
              {m.streaming && <span className="message-cursor">▌</span>}
            </div>
          )
        )}
        <div ref={messagesEndRef} />
        {showScrollToBottom && (
          <div className="chat-scroll-to-bottom-wrap">
            <button
              type="button"
              className="chat-scroll-to-bottom"
              onClick={scrollToBottom}
              aria-label="Scroll to bottom"
            >
              ↓
            </button>
          </div>
        )}
      </div>
      <form onSubmit={handleSubmit} className="chat-form">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              if (input.trim() && !isStreaming) handleSubmit(e);
            }
          }}
          placeholder="Message… (Shift+Enter for new line)"
          className="chat-input"
          rows={1}
        />
        <button type="submit" disabled={isStreaming || !input.trim()} className="btn btn-primary">
          Send
        </button>
      </form>
      </div>
      {showDeleteConfirm && (
        <ConfirmModal
          title="Delete chat?"
          message="This cannot be undone."
          confirmLabel="Delete"
          cancelLabel="Cancel"
          danger
          onConfirm={handleDeleteConfirm}
          onCancel={() => setShowDeleteConfirm(false)}
        />
      )}
    </div>
  );
}
