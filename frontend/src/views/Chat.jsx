import { useCallback, useEffect, useRef, useState } from "react";
import { api, chatSocket } from "../api";
import { useAuth } from "../auth.jsx";
import { useT } from "../i18n.jsx";

const fmtTime = (iso) => {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch (_) {
    return "";
  }
};

export default function Chat() {
  const { t } = useT();
  const { user } = useAuth();
  const [contacts, setContacts] = useState([]);
  const [active, setActive] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState(null);
  const wsRef = useRef(null);
  const endRef = useRef(null);
  const activeRef = useRef(null);
  activeRef.current = active;

  const loadContacts = useCallback(async () => {
    try {
      setContacts(await api.chatContacts());
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    loadContacts();
  }, [loadContacts]);

  // Single WebSocket for realtime inbound/echo messages.
  useEffect(() => {
    const ws = chatSocket();
    wsRef.current = ws;
    ws.onmessage = (ev) => {
      try {
        const payload = JSON.parse(ev.data);
        if (payload.type !== "message") return;
        const m = payload.data;
        const cur = activeRef.current;
        const relevant =
          cur && (m.sender_id === cur.user.id || m.recipient_id === cur.user.id);
        if (relevant) {
          setMessages((prev) =>
            prev.some((x) => x.id === m.id) ? prev : [...prev, m]
          );
        }
        loadContacts();
      } catch (_) {
        /* ignore */
      }
    };
    return () => ws.close();
  }, [loadContacts]);

  const openContact = async (c) => {
    setActive(c);
    setError(null);
    try {
      setMessages(await api.chatHistory(c.user.id));
      loadContacts();
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (e) => {
    e.preventDefault();
    const body = draft.trim();
    if (!body || !active) return;
    setDraft("");
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ recipient_id: active.user.id, body }));
    } else {
      try {
        const m = await api.chatSend(active.user.id, body);
        setMessages((prev) => [...prev, m]);
      } catch (err) {
        setError(err.message);
      }
    }
  };

  return (
    <div className="view">
      <div className="panel">
        <h3>
          <span>{t("chat.title")}</span>
          <span className="muted">{t("chat.subtitle")}</span>
        </h3>
        <div className="chat">
          <div className="chat-contacts">
            {contacts.length === 0 && <div className="muted pad">{t("chat.noContacts")}</div>}
            {contacts.map((c) => (
              <button
                key={c.user.id}
                className={`contact ${active?.user.id === c.user.id ? "active" : ""}`}
                onClick={() => openContact(c)}
              >
                <div className="contact-top">
                  <span className="contact-name">
                    {c.user.display_name || c.user.email}
                    {c.user.role === "superuser" && (
                      <span className="tag support">{t("chat.support")}</span>
                    )}
                  </span>
                  {c.unread > 0 && <span className="unread">{c.unread}</span>}
                </div>
                {c.last_message && (
                  <div className="contact-last muted">{c.last_message.body}</div>
                )}
              </button>
            ))}
          </div>

          <div className="chat-thread">
            {error && <div className="error">⚠ {error}</div>}
            {!active ? (
              <div className="muted pad">{t("chat.selectContact")}</div>
            ) : (
              <>
                <div className="chat-messages">
                  {messages.length === 0 && (
                    <div className="muted pad">{t("chat.empty")}</div>
                  )}
                  {messages.map((m) => {
                    const mine = m.sender_id === user?.id;
                    return (
                      <div key={m.id} className={`bubble-row ${mine ? "mine" : "theirs"}`}>
                        <div className="bubble">
                          <div className="bubble-body">{m.body}</div>
                          <div className="bubble-time">{fmtTime(m.created_at)}</div>
                        </div>
                      </div>
                    );
                  })}
                  <div ref={endRef} />
                </div>
                <form className="chat-input" onSubmit={send}>
                  <input
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    placeholder={t("chat.placeholder")}
                  />
                  <button type="submit">{t("chat.send")}</button>
                </form>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
