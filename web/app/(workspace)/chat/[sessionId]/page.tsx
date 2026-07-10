"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import ChatMessages, { type Message } from "@/components/chat/ChatMessages";
import ChatComposer, { type SendOptions } from "@/components/chat/ChatComposer";
import { MessageSquare, Wifi, WifiOff } from "lucide-react";
import { ChatStream, type ConnectionStatus } from "@/lib/chat-stream";
import { sessions, type RetrievalDetails, type SessionDetail } from "@/lib/api";
import { useTypewriter } from "@/lib/use-typewriter";

export default function ChatSessionPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("disconnected");
  const [editContent, setEditContent] = useState<string | null>(null);

  // Refs to track retrieval/reasoning state during streaming (avoids stale closures)
  const retrievalRef = useRef<RetrievalDetails | null>(null);
  const reasoningRef = useRef("");
  const streamStartedRef = useRef(false);

  // ChatStream instance — stable across renders
  const streamRef = useRef<ChatStream | null>(null);

  // Typewriter: streams content character by character
  const { appendToBuffer } = useTypewriter({
    streaming,
    onChar: (char) => {
      setSession((prev) => {
        if (!prev) return prev;
        const messages = [...prev.messages];
        const last = messages[messages.length - 1];
        if (last && last.role === "assistant") {
          messages[messages.length - 1] = { ...last, content: last.content + char };
        }
        return { ...prev, messages };
      });
    },
    onFlush: (remaining) => {
      setSession((prev) => {
        if (!prev) return prev;
        const messages = [...prev.messages];
        const last = messages[messages.length - 1];
        if (last && last.role === "assistant") {
          messages[messages.length - 1] = { ...last, content: last.content + remaining };
        }
        return { ...prev, messages };
      });
    },
  });

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
        if (!streamStartedRef.current) {
          streamStartedRef.current = true;
          setSession((prev) => {
            if (!prev) return prev;
            const messages = [...prev.messages];
            const metadata: Message["metadata"] = {};
            if (retrievalRef.current) {
              metadata.retrieval_details = retrievalRef.current;
            }
            if (reasoningRef.current) {
              metadata.reasoning_text = reasoningRef.current;
            }
            retrievalRef.current = null;
            reasoningRef.current = "";
            messages.push({
              id: "streaming",
              role: "assistant",
              content: "",
              created_at: new Date().toISOString(),
              metadata,
            });
            return { ...prev, messages };
          });
        }
        appendToBuffer(content);
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
        streamStartedRef.current = false;
        // Lightweight background refresh for header (title, count) without
        // replacing messages to avoid flicker
        sessions.get(sessionId).then((data) => {
          setSession((prev) => {
            if (!prev) return prev;
            // Only update metadata, keep current messages intact
            return { ...data, messages: prev.messages };
          });
          // Notify sidebar to refresh session list
          window.dispatchEvent(new CustomEvent("session-updated"));
        }).catch(() => {});
      },

      onError: (message) => {
        setStreaming(false);
        streamStartedRef.current = false;
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
    (content: string, options?: SendOptions) => {
      const stream = streamRef.current;
      if (!stream) return;

      streamStartedRef.current = false;

      // Add user message to local state immediately (optimistic)
      const userMessage: Message = {
        id: `user-${Date.now()}`,
        role: "user",
        content,
        created_at: new Date().toISOString(),
      };
      setSession((prev) => {
        if (!prev) return prev;
        return { ...prev, messages: [...prev.messages, userMessage] };
      });

      setStreaming(true);
      setEditContent(null);
      stream.sendQuery(content, options?.model);
    },
    []
  );

  const handleRegenerate = useCallback(() => {
    if (!session || streaming) return;
    const stream = streamRef.current;
    if (!stream) return;

    const lastUserMsg = [...session.messages].reverse().find((m) => m.role === "user");
    if (!lastUserMsg) return;

    // Remove the last assistant message(s) after the last user message
    const lastUserIdx = session.messages.lastIndexOf(lastUserMsg);
    const trimmedMessages = session.messages.slice(0, lastUserIdx + 1);

    setSession((prev) => {
      if (!prev) return prev;
      return { ...prev, messages: trimmedMessages };
    });

    setStreaming(true);
    stream.sendQuery(lastUserMsg.content);
  }, [session, streaming]);

  const handleEdit = useCallback((content: string) => {
    setEditContent(content);
    // Scroll to the composer
    window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
  }, []);

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
              {session?.title || "新对话"}
            </h1>
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
            onRegenerate={handleRegenerate}
            onEdit={handleEdit}
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
        editValue={editContent}
      />
    </div>
  );
}
