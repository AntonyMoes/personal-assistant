import { useState, useEffect, useLayoutEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getChat, getChatMessages, updateChat } from '../api/chats';
import { useChatWebSocket } from '../ws/useChatWebSocket';

export default function ChatPage() {
  const { chatId } = useParams();
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const [chat, setChat] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleValue, setTitleValue] = useState('');
  const [focusInputAfterSend, setFocusInputAfterSend] = useState(false);

  const { sendMessage, sendInterrupt, isStreaming, lastError, connect, connected } = useChatWebSocket(chatId, {
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
    if (chatId) connect();
    return () => {};
  }, [chatId, connect]);

  useEffect(() => {
    if (lastError) setError(lastError);
  }, [lastError]);

  useLayoutEffect(() => {
    if (focusInputAfterSend && !editingTitle) {
      inputRef.current?.focus();
      setFocusInputAfterSend(false);
    }
  }, [focusInputAfterSend, editingTitle]);

  useLayoutEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

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
          </h1>
        )}
        {isStreaming && (
          <button type="button" className="btn btn-small" onClick={sendInterrupt}>
            Stop
          </button>
        )}
      </div>
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">Send a message to start.</div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`message message-${m.role}`}>
            <div className="message-content">{m.content || '\u00a0'}</div>
            {m.reasoning && <div className="message-reasoning">{m.reasoning}</div>}
            {m.streaming && <span className="message-cursor">▌</span>}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
      <form onSubmit={handleSubmit} className="chat-form">
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Message…"
          className="chat-input"
        />
        <button type="submit" disabled={isStreaming || !input.trim()} className="btn btn-primary">
          Send
        </button>
      </form>
      </div>
    </div>
  );
}
