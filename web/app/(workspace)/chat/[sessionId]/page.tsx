"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import ChatMessages, { type Message } from "@/components/chat/ChatMessages";
import ChatComposer from "@/components/chat/ChatComposer";
import { MessageSquare, Wifi, WifiOff } from "lucide-react";
import { ChatStream, type ConnectionStatus, type RetrievalDetails } from "@/lib/chat-stream";
import { sessions, type SessionDetail } from "@/lib/api";

export default function ChatSessionPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("disconnected");

  // Refs to track retrieval/reasoning state during streaming (avoids stale closures)
  const retrievalRef = useRef<RetrievalDetails | null>(null);
  const reasoningRef = useRef("");

  // ChatStream instance — stable across renders
  const streamRef = useRef<ChatStream | null>(null);

  // Load session data
  const loadSession = useCallback(() => {
    if (!sessionId) return;
    sessions
      .get(sessionId)
      .then((data) => setSession(data))
      .catch(() => router.push("/chat"));
  }, [sessionId, router]);

  useEffect(() => {
    loadSession();
  }, [loadSession]);

  // WebSocket connection via ChatStream
  useEffect(() => {
    const stream = new ChatStream(sessionId, {
      onChunk: (content) => {
        setSession((prev) => {
          if (!prev) return prev;
          const messages = [...prev.messages];
          const last = messages[messages.length - 1];

          if (last && last.role === "assistant") {
            // Append to existing assistant message
            messages[messages.length - 1] = {
              ...last,
              content: last.content + content,
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
              content,
              created_at: new Date().toISOString(),
              metadata,
            });
            retrievalRef.current = null;
            reasoningRef.current = "";
          }
          return { ...prev, messages };
        });
      },

      onReasoning: (content) => {
        reasoningRef.current += content;
      },

      onRetrievalDone: (details) => {
        retrievalRef.current = details;
      },

      onDone: () => {
        setStreaming(false);
        retrievalRef.current = null;
        reasoningRef.current = "";
        // Reload session to get proper IDs and persisted metadata
        loadSession();
      },

      onError: (message) => {
        setStreaming(false);
        console.error("ChatStream error:", message);
      },

      onStatusChange: (status) => {
        setConnectionStatus(status);
        if (status === "disconnected") setStreaming(false);
      },
    });

    streamRef.current = stream;
    stream.connect();

    return () => {
      stream.disconnect();
      streamRef.current = null;
    };
  }, [sessionId, loadSession]);

  const sendMessage = useCallback(
    (content: string, model?: string) => {
      const stream = streamRef.current;
      if (!stream) return;

      setStreaming(true);
      stream.sendQuery(content, model);
    },
    []
  );

  const isConnected = connectionStatus === "connected";

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
            isConnected
              ? "bg-[var(--success-soft)] text-[var(--success)]"
              : "bg-[var(--warning-soft)] text-[var(--warning)]"
          }`}
        >
          {isConnected ? <Wifi size={13} /> : <WifiOff size={13} />}
          {isConnected ? "已连接" : "连接中"}
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-auto">
        {session ? (
          <ChatMessages
            messages={session.messages as Message[]}
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
        disabled={!isConnected || streaming}
        placeholder={streaming ? "正在生成回答..." : "输入你的问题..."}
      />
    </div>
  );
}
