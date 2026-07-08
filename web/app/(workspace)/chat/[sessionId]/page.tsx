"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import ChatMessages, { type Message, type RetrievalDetails } from "@/components/chat/ChatMessages";
import ChatComposer from "@/components/chat/ChatComposer";
import { MessageSquare, Wifi, WifiOff } from "lucide-react";

interface SessionData {
  id: string;
  title: string;
  messages: Message[];
}

export default function ChatSessionPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;
  const [session, setSession] = useState<SessionData | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [ws, setWs] = useState<WebSocket | null>(null);

  // Refs to track retrieval/reasoning state during streaming (avoids stale closures)
  const retrievalRef = useRef<RetrievalDetails | null>(null);
  const reasoningRef = useRef("");

  // Load session data
  useEffect(() => {
    if (!sessionId) return;
    fetch(`/api/sessions/${sessionId}`)
      .then((res) => {
        if (!res.ok) throw new Error("Session deleted");
        return res.json();
      })
      .then((data) => setSession(data))
      .catch(() => router.push("/chat"));
  }, [router, sessionId]);

  // WebSocket connection
  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/api/ws/chat`;

    const socket = new WebSocket(wsUrl);

    socket.onopen = () => setWs(socket);

    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        if (msg.type === "retrieval_done") {
          // Store retrieval details for the upcoming assistant message
          const { type, ...details } = msg;
          retrievalRef.current = details;
        } else if (msg.type === "reasoning") {
          // Accumulate reasoning text
          reasoningRef.current += msg.content;
        } else if (msg.type === "chunk") {
          setSession((prev) => {
            if (!prev) return prev;
            const messages = [...prev.messages];
            const last = messages[messages.length - 1];

            if (last && last.role === "assistant") {
              // Append to existing assistant message
              messages[messages.length - 1] = {
                ...last,
                content: last.content + msg.content,
              };
            } else {
              // Create new assistant message with retrieval/reasoning metadata
              const metadata: Message["metadata"] = {};
              if (retrievalRef.current) {
                metadata.retrieval_details = retrievalRef.current;
              }
              if (reasoningRef.current) {
                metadata.reasoning_text = reasoningRef.current;
              }
              messages.push({
                id: "streaming",
                role: "assistant",
                content: msg.content,
                created_at: new Date().toISOString(),
                metadata,
              });
              // Clear refs for next message
              retrievalRef.current = null;
              reasoningRef.current = "";
            }
            return { ...prev, messages };
          });
        } else if (msg.type === "done") {
          setStreaming(false);
          retrievalRef.current = null;
          reasoningRef.current = "";
          // Reload session to get proper IDs and persisted metadata
          fetch(`/api/sessions/${msg.session_id || sessionId}`)
            .then((res) => res.json())
            .then((data) => setSession(data))
            .catch(console.error);
        } else if (msg.type === "error") {
          setStreaming(false);
          console.error("WS error:", msg.message);
        }
      } catch (e) {
        console.error("WS parse error", e);
      }
    };

    socket.onclose = () => {
      setWs(null);
      setStreaming(false);
    };

    socket.onerror = () => {
      setWs(null);
      setStreaming(false);
    };

    return () => {
      socket.close();
    };
  }, [sessionId]);

  const sendMessage = useCallback(
    (content: string) => {
      if (!ws || ws.readyState !== WebSocket.OPEN) return;

      setStreaming(true);
      ws.send(
        JSON.stringify({
          type: "query",
          content,
          session_id: sessionId,
        })
      );
    },
    [ws, sessionId]
  );

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-[var(--surface-border)] bg-[var(--surface-panel)] px-4 lg:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <div className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-[var(--accent-soft)] text-[var(--accent)]">
            <MessageSquare size={17} />
          </div>
          <div className="min-w-0">
            <h1 className="truncate text-sm font-semibold">
              {session?.title || "会话"}
            </h1>
            <p className="text-xs text-[var(--text-secondary)]">
              {session?.messages.length ?? 0} 条消息
            </p>
          </div>
        </div>
        <div
          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
            ws?.readyState === WebSocket.OPEN
              ? "bg-[var(--success-soft)] text-[var(--success)]"
              : "bg-[var(--warning-soft)] text-[var(--warning)]"
          }`}
        >
          {ws?.readyState === WebSocket.OPEN ? <Wifi size={13} /> : <WifiOff size={13} />}
          {ws?.readyState === WebSocket.OPEN ? "已连接" : "连接中"}
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-auto">
        {session ? (
          <ChatMessages
            messages={session.messages}
            streaming={streaming}
          />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-[var(--text-secondary)]">
            正在加载会话...
          </div>
        )}
      </div>
      <ChatComposer
        onSend={sendMessage}
        disabled={!ws || ws.readyState !== WebSocket.OPEN || streaming}
        placeholder={streaming ? "正在生成回答..." : "输入你的问题..."}
      />
    </div>
  );
}
