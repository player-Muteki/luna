"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import ChatMessages from "@/components/chat/ChatMessages";
import ChatComposer from "@/components/chat/ChatComposer";

interface SessionData {
  id: string;
  title: string;
  messages: { id: string; role: string; content: string; created_at: string }[];
}

export default function ChatSessionPage() {
  const params = useParams();
  const sessionId = params.sessionId as string;
  const [session, setSession] = useState<SessionData | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Load session data
  useEffect(() => {
    if (!sessionId) return;
    fetch(`/api/sessions/${sessionId}`)
      .then((res) => res.json())
      .then((data) => setSession(data))
      .catch(console.error);
  }, [sessionId]);

  // WebSocket connection
  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    // For dev mode with proxied API
    const wsUrl = `${protocol}//${host}/api/ws/chat`;

    const socket = new WebSocket(wsUrl);
    wsRef.current = socket;

    socket.onopen = () => setWs(socket);

    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "chunk") {
          setSession((prev) => {
            if (!prev) return prev;
            const messages = [...prev.messages];
            const last = messages[messages.length - 1];
            if (last && last.role === "assistant") {
              messages[messages.length - 1] = {
                ...last,
                content: last.content + msg.content,
              };
            } else {
              messages.push({
                id: "streaming",
                role: "assistant",
                content: msg.content,
                created_at: new Date().toISOString(),
              });
            }
            return { ...prev, messages };
          });
        } else if (msg.type === "done") {
          setStreaming(false);
          // Reload session to get proper IDs
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
    <div className="h-full flex flex-col">
      <div className="flex-1 overflow-auto">
        {session ? (
          <ChatMessages
            messages={session.messages}
            streaming={streaming}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-[var(--text-secondary)]">
            加载中...
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
