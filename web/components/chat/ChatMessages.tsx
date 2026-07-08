"use client";

import { useEffect, useRef } from "react";

interface Message {
  id: string;
  role: string;
  content: string;
  created_at: string;
}

export default function ChatMessages({
  messages,
  streaming,
}: {
  messages: Message[];
  streaming: boolean;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming]);

  if (messages.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-[var(--text-secondary)] p-8 text-center">
        <div>
          <p className="text-lg mb-2">开始提问</p>
          <p className="text-sm">在下方输入框中输入你的问题，RAG 系统将从文档中检索相关上下文并生成回答。</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
        >
          <div
            className={`max-w-[80%] rounded-lg px-4 py-3 text-sm ${
              msg.role === "user"
                ? "bg-[var(--accent)] text-white"
                : "bg-[var(--surface-alt)] text-[var(--text-primary)]"
            }`}
          >
            <div className="whitespace-pre-wrap break-words">
              {msg.content}
              {streaming && msg === messages[messages.length - 1] && msg.role === "assistant" && (
                <span className="inline-block w-2 h-4 bg-[var(--accent)] animate-pulse ml-1" />
              )}
            </div>

            {msg.role === "assistant" && msg.content && (
              <div className="mt-2 text-xs text-[var(--text-secondary)]">
                {new Date(msg.created_at).toLocaleTimeString("zh-CN", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </div>
            )}
          </div>
        </div>
      ))}

      {/* Loading indicator when streaming hasn't started yet */}
      {streaming && messages.length > 0 && messages[messages.length - 1].role === "user" && (
        <div className="flex justify-start">
          <div className="bg-[var(--surface-alt)] rounded-lg px-4 py-3 text-sm">
            <div className="flex gap-1">
              <span className="w-2 h-2 bg-[var(--text-secondary)] rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
              <span className="w-2 h-2 bg-[var(--text-secondary)] rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
              <span className="w-2 h-2 bg-[var(--text-secondary)] rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
