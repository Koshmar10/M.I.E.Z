import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, errorMessage } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import Markdown from "../common/Markdown";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface SessionSummary {
  id: number;
  created_at: string;
  updated_at: string;
  message_count: number;
  preview: string;
}

type View = "list" | "chat";

interface RoleConfig {
  greeting: string;
  suggested: string[];
}

const ROLE_CONFIG: Record<string, RoleConfig> = {
  CEO: {
    greeting: "Hello! I'm MIEZ, your executive AI assistant. I can give you a full business overview — ask me anything.",
    suggested: [
      "Give me a full business summary for today",
      "Which department has the most issues?",
      "What is our profit this month?",
    ],
  },
  HR: {
    greeting: "Hello! I'm MIEZ, your HR assistant. I can help you with employee data, leave requests, and department summaries.",
    suggested: [
      "Show me the HR dashboard summary",
      "List active employees in the company",
      "How many leave requests are pending?",
    ],
  },
  IT: {
    greeting: "Hello! I'm MIEZ, your IT assistant. I can help you track tickets, check system status, and manage support requests.",
    suggested: [
      "Show me all open tickets",
      "List urgent and high priority tickets",
      "Create a new support ticket",
    ],
  },
  SALES: {
    greeting: "Hello! I'm MIEZ, your sales assistant. I can help you track orders, customers, and revenue.",
    suggested: [
      "Show me the sales dashboard summary",
      "List the most recent orders",
      "Show me pending orders",
    ],
  },
  INVENTORY: {
    greeting: "Hello! I'm MIEZ, your inventory assistant. I can help you check stock levels, products, and suppliers.",
    suggested: [
      "Show me products below minimum stock",
      "List out of stock products",
      "Show me all products in a category",
    ],
  },
};

const SESSION_KEY = (userId: number) => `miez_session_${userId}`;

const formatDate = (iso: string) => {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
};

const MiezAssistant = () => {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<View>("list");

  // List view state
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);

  // Chat view state
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [restoring, setRestoring] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);

  const fetchSessions = useCallback(async () => {
    setLoadingSessions(true);
    try {
      setSessions(await api.get<SessionSummary[]>("/api/assistant/sessions/"));
    } catch {
      // keep the list as it was
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  const loadSession = useCallback(async (id: number) => {
    setRestoring(true);
    try {
      const data = await api.get<{ id: number; messages: Message[] }>(`/api/assistant/sessions/${id}/`);
      setSessionId(data.id);
      setMessages(data.messages.map((m) => ({ role: m.role, content: m.content })));
      return true;
    } catch (err) {
      // a session that no longer exists shouldn't be reopened next time
      if (err instanceof ApiError && user) localStorage.removeItem(SESSION_KEY(user.id));
      return false;
    } finally {
      setRestoring(false);
    }
  }, [user]);

  // On open: check localStorage for active session, else show list
  useEffect(() => {
    if (!open || !user) return;

    const stored = localStorage.getItem(SESSION_KEY(user.id));
    if (stored) {
      const id = parseInt(stored, 10);
      if (!isNaN(id) && sessionId !== id) {
        loadSession(id).then((ok) => {
          if (ok) {
            setView("chat");
          } else {
            setView("list");
            fetchSessions();
          }
        });
      }
    } else {
      setView("list");
      fetchSessions();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (open && view === "chat") {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, open, view]);

  if (!user) return null;

  const goToList = () => {
    setView("list");
    fetchSessions();
  };

  const openSession = async (id: number) => {
    const ok = await loadSession(id);
    if (ok) {
      localStorage.setItem(SESSION_KEY(user.id), String(id));
      setView("chat");
    }
  };

  const startNewChat = () => {
    setSessionId(null);
    setMessages([]);
    setInput("");
    if (user) localStorage.removeItem(SESSION_KEY(user.id));
    setView("chat");
  };

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setInput("");
    setLoading(true);

    try {
      const data = await api.post<{ response: string; session_id?: number }>("/api/assistant/chat/", {
        message: trimmed,
        current_page: window.location.pathname,
        ...(sessionId ? { session_id: sessionId } : {}),
      });
      if (!sessionId && data.session_id) {
        setSessionId(data.session_id);
        localStorage.setItem(SESSION_KEY(user.id), String(data.session_id));
      }
      setMessages((prev) => [...prev, { role: "assistant", content: data.response }]);
    } catch (err) {
      const content = err instanceof ApiError ? errorMessage(err, "Something went wrong.") : "Could not reach the assistant.";
      setMessages((prev) => [...prev, { role: "assistant", content }]);
    } finally {
      setLoading(false);
    }
  };

  const deleteSession = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    await api.delete(`/api/assistant/sessions/${id}/`);
    if (user && localStorage.getItem(SESSION_KEY(user.id)) === String(id)) {
      localStorage.removeItem(SESSION_KEY(user.id));
    }
    setSessions((prev) => prev.filter((s) => s.id !== id));
  };

  return (
    <>
      {open && (
        <div className="fixed bottom-16 right-4 z-50 w-[360px] flex flex-col rounded-2xl shadow-2xl border border-gray-200 overflow-hidden bg-white">
          {/* Header */}
          <div className="flex items-center gap-3 px-4 py-3 bg-gray-900 text-white">
            {view === "chat" && (
              <button
                onClick={goToList}
                className="text-gray-400 hover:text-white cursor-pointer text-lg leading-none"
                title="Back to conversations"
              >
                ←
              </button>
            )}
            <div className="h-8 w-8 rounded-full bg-red-500 flex items-center justify-center text-sm font-bold shrink-0">M</div>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-sm leading-tight">MIEZ Assistant</div>
              <div className="text-xs text-gray-400">{view === "chat" ? "AI-powered · always on" : "Your conversations"}</div>
            </div>
            {view === "chat" && (
              <button
                onClick={startNewChat}
                className="text-gray-400 hover:text-white text-xs cursor-pointer px-1"
                title="New conversation"
              >
                New
              </button>
            )}
            {view === "list" && (
              <button
                onClick={startNewChat}
                className="text-xs text-gray-400 hover:text-white cursor-pointer border border-gray-600 rounded-md px-2 py-0.5"
              >
                + New
              </button>
            )}
            <button onClick={() => setOpen(false)} className="text-gray-400 hover:text-white text-lg leading-none cursor-pointer">
              ✕
            </button>
          </div>

          {/* List view */}
          {view === "list" && (
            <div className="flex-1 overflow-y-auto max-h-[460px] min-h-[200px] bg-gray-50">
              {loadingSessions ? (
                <div className="p-4 text-sm text-gray-400">Loading conversations…</div>
              ) : sessions.length === 0 ? (
                <div className="p-6 flex flex-col items-center gap-3 text-center">
                  <div className="text-gray-400 text-sm">No conversations yet.</div>
                  <button
                    onClick={startNewChat}
                    className="text-sm px-4 py-2 rounded-lg bg-gray-900 text-white hover:bg-gray-800 cursor-pointer"
                  >
                    Start a conversation
                  </button>
                </div>
              ) : (
                <ul className="divide-y divide-gray-100">
                  {sessions.map((s) => (
                    <li
                      key={s.id}
                      onClick={() => openSession(s.id)}
                      className="flex items-start gap-3 px-4 py-3 hover:bg-white cursor-pointer group"
                    >
                      <div className="h-8 w-8 rounded-full bg-red-100 flex items-center justify-center text-red-500 text-xs font-bold shrink-0 mt-0.5">M</div>
                      <div className="flex-1 min-w-0">
                        <div className="text-xs text-gray-400 mb-0.5">{formatDate(s.updated_at)} · {s.message_count} messages</div>
                        <div className="text-sm text-gray-700 truncate">{s.preview || "Empty conversation"}</div>
                      </div>
                      <button
                        onClick={(e) => deleteSession(e, s.id)}
                        className="text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer text-sm shrink-0 mt-1"
                        title="Delete"
                      >
                        ✕
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* Chat view */}
          {view === "chat" && (
            <>
              <div className="flex-1 overflow-y-auto p-4 space-y-3 max-h-[400px] min-h-[200px] bg-gray-50">
                {restoring ? (
                  <div className="text-sm text-gray-400">Restoring conversation…</div>
                ) : messages.length === 0 ? (
                  <div className="space-y-3">
                    {(() => {
                      const config = ROLE_CONFIG[user.role] ?? ROLE_CONFIG.CEO;
                      return (
                        <>
                          <div className="bg-white border border-gray-200 rounded-xl px-4 py-3 text-sm text-gray-700 shadow-sm">
                            {config.greeting}
                          </div>
                          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide pt-1">Suggested</div>
                          <div className="space-y-2">
                            {config.suggested.map((s) => (
                              <button
                                key={s}
                                onClick={() => send(s)}
                                className="w-full text-left text-sm px-3 py-2 rounded-lg border border-red-200 text-red-700 bg-red-50 hover:bg-red-100 transition-colors cursor-pointer"
                              >
                                {s}
                              </button>
                            ))}
                          </div>
                        </>
                      );
                    })()}
                  </div>
                ) : (
                  messages.map((m, i) => (
                    <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                      <div
                        className={`max-w-[85%] text-sm px-3 py-2 rounded-xl ${
                          m.role === "user"
                            ? "bg-gray-900 text-white rounded-br-sm whitespace-pre-wrap"
                            : "bg-white border border-gray-200 text-gray-800 rounded-bl-sm shadow-sm"
                        }`}
                      >
                        {m.role === "assistant" ? (
                          <Markdown variant="chat">{m.content}</Markdown>
                        ) : (
                          m.content
                        )}
                      </div>
                    </div>
                  ))
                )}
                {loading && (
                  <div className="flex justify-start">
                    <div className="bg-white border border-gray-200 rounded-xl rounded-bl-sm px-3 py-2 text-sm text-gray-400 shadow-sm">
                      Thinking…
                    </div>
                  </div>
                )}
                <div ref={bottomRef} />
              </div>

              <div className="flex items-center gap-2 px-3 py-3 border-t border-gray-200 bg-white">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && send(input)}
                  placeholder="Type a message..."
                  disabled={loading || restoring}
                  className="flex-1 text-sm px-3 py-2 rounded-lg border border-gray-200 focus:outline-none focus:ring-1 focus:ring-gray-300 bg-gray-50 disabled:opacity-50"
                />
                <button
                  onClick={() => send(input)}
                  disabled={loading || restoring || !input.trim()}
                  className="h-9 w-9 rounded-full bg-red-400 hover:bg-red-500 flex items-center justify-center text-white disabled:opacity-40 cursor-pointer transition-colors shrink-0"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {/* Toggle pill */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-4 right-4 z-50 flex items-center gap-2 px-4 py-2 rounded-full bg-gray-900 text-white text-sm font-medium shadow-lg hover:bg-gray-800 transition-colors cursor-pointer"
      >
        <span className="h-2 w-2 rounded-full bg-green-400" />
        <div className="h-5 w-5 rounded-full bg-red-500 flex items-center justify-center text-xs font-bold">M</div>
        MIEZ Assistant
        <span className="text-gray-400 text-xs">{open ? "∨" : "∧"}</span>
      </button>
    </>
  );
};

export default MiezAssistant;
