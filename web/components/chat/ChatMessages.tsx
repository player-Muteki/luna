"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, ChevronDown, ChevronRight, Copy, Check, UserRound, ThumbsUp, ThumbsDown, RefreshCw, Pencil } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeHighlight from "rehype-highlight";

export interface RetrievalDetails {
  mode: string;
  elapsed_ms: number;
  total_candidates: number;
  effective_query: string;
  results: Array<{
    chunk_id: string;
    source_path: string;
    file_name: string;
    score: number;
    matched_by: string[];
    vector_score?: number | null;
    bm25_score?: number | null;
  }>;
}

export interface Message {
  id: string;
  role: string;
  content: string;
  created_at: string;
  metadata?: {
    retrieval_details?: RetrievalDetails;
    reasoning_text?: string;
  };
}

function CollapsibleSection({
  title,
  defaultOpen = false,
  children,
  indent = false,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
  indent?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className={indent ? "-mx-3" : ""}>
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-1.5 rounded-md px-3 py-1.5 text-left text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-alt)] hover:text-[var(--text-primary)]"
      >
        {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        {title}
      </button>
      {open && <div className="px-3 pb-2">{children}</div>}
    </div>
  );
}

function RetrievalPanel({ details }: { details: RetrievalDetails }) {
  return (
    <CollapsibleSection title="知识库检索过程" indent>
      <div className="space-y-2 text-xs">
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[var(--text-secondary)]">
          <div>
            检索模式：<span className="font-medium text-[var(--text-primary)]">{details.mode}</span>
          </div>
          <div>
            耗时：<span className="font-medium text-[var(--text-primary)]">{details.elapsed_ms}ms</span>
          </div>
          <div>
            候选数：<span className="font-medium text-[var(--text-primary)]">{details.total_candidates}</span>
          </div>
          {details.effective_query && (
            <div className="col-span-2">
              优化查询：<span className="font-medium text-[var(--text-primary)]">{details.effective_query}</span>
            </div>
          )}
        </div>
        {details.results.length > 0 && (
          <div className="space-y-1 pt-1">
            <p className="text-[var(--text-muted)]">匹配片段（前 {details.results.length} 条）：</p>
            {details.results.map((r, i) => (
              <div
                key={r.chunk_id}
                className="flex items-center justify-between rounded-md border border-[var(--surface-border)] bg-[var(--surface-bg)] px-2.5 py-1.5"
              >
                <div className="flex min-w-0 items-center gap-2">
                  <span className="shrink-0 text-[var(--text-muted)]">[{i + 1}]</span>
                  <span className="truncate font-mono text-xs">{r.source_path}</span>
                  <div className="flex shrink-0 gap-1">
                    {r.matched_by.map((m) => (
                      <span
                        key={m}
                        className="rounded bg-[var(--accent-soft)] px-1.5 py-0.5 text-[10px] font-medium text-[var(--accent)]"
                      >
                        {m}
                      </span>
                    ))}
                  </div>
                </div>
                <span className="ml-2 shrink-0 text-[var(--text-muted)]">
                  {(r.score * 100).toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </CollapsibleSection>
  );
}

function CopyButton({ content }: { content: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API not available
    }
  };

  return (
    <button
      onClick={handleCopy}
      className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-alt)] hover:text-[var(--text-primary)]"
      title="复制文本"
    >
      {copied ? (
        <>
          <Check size={12} />
          已复制
        </>
      ) : (
        <>
          <Copy size={12} />
          复制文本
        </>
      )}
    </button>
  );
}

/** Code block with a copy button overlay in the top-right corner. */
function CodeBlock({ children, className }: { children?: React.ReactNode; className?: string }) {
  const [copied, setCopied] = useState(false);
  // Extract code text from children for copying
  const code = useRef<HTMLPreElement>(null);

  const handleCopy = async () => {
    const text = code.current?.textContent || "";
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API not available
    }
  };

  return (
    <div className="group relative">
      <pre ref={code} className={className}>{children}</pre>
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 rounded-md bg-[var(--surface-panel)] p-1.5 text-[var(--text-muted)] opacity-0 transition-opacity group-hover:opacity-100 hover:text-[var(--text-primary)]"
        title="复制代码"
      >
        {copied ? <Check size={14} /> : <Copy size={14} />}
      </button>
    </div>
  );
}

export default function ChatMessages({
  messages,
  streaming,
  onRegenerate,
  onEdit,
}: {
  messages: Message[];
  streaming: boolean;
  onRegenerate?: () => void;
  onEdit?: (content: string) => void;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [feedback, setFeedback] = useState<Partial<Record<string, "like" | "dislike">>>({});

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming]);

  if (messages.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-center text-[var(--text-secondary)]">
        <div>
          <div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-lg bg-[var(--surface-alt)] text-[var(--text-muted)]">
            <Bot size={24} />
          </div>
          <p className="text-base font-medium text-[var(--text-primary)]">还没有消息</p>
          <p className="mt-1 text-sm">等待第一条问题。</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-5 px-4 py-6 lg:px-6">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
        >
          {msg.role !== "user" && (
            <div className="mt-1 grid h-8 w-8 shrink-0 place-items-center rounded-md bg-[var(--surface-panel)] text-[var(--accent)] shadow-[var(--shadow-sm)]">
              <Bot size={17} />
            </div>
          )}
          <div
            className={`max-w-[82%] rounded-lg px-4 py-3 text-sm leading-6 shadow-[var(--shadow-sm)] ${
              msg.role === "user"
                ? "bg-[var(--accent)] text-white"
                : "border border-[var(--surface-border)] bg-[var(--surface-panel)] text-[var(--text-primary)]"
            }`}
          >
            {/* Assistant-only panels: retrieval & reasoning */}
            {msg.role !== "user" && msg.metadata?.retrieval_details && (
              <RetrievalPanel details={msg.metadata.retrieval_details} />
            )}
            {msg.role !== "user" && msg.metadata?.reasoning_text && (
              <CollapsibleSection title="大模型推理过程" indent>
                <div className="whitespace-pre-wrap break-words text-xs leading-5 text-[var(--text-secondary)] italic">
                  {msg.metadata.reasoning_text}
                </div>
              </CollapsibleSection>
            )}

            {/* Main content — markdown reading view */}
            {msg.role !== "user" && msg.content ? (
              <div className="prose prose-sm max-w-none">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkMath]}
                  rehypePlugins={[rehypeKatex, rehypeHighlight]}
                  components={{
                    pre: ({ className, children }) => (
                      <CodeBlock className={className}>{children}</CodeBlock>
                    ),
                  }}
                >
                  {msg.content}
                </ReactMarkdown>
                {streaming && msg === messages[messages.length - 1] && msg.role === "assistant" && (
                  <span className="inline-block w-2 h-4 bg-[var(--accent)] animate-pulse ml-0.5 align-middle" />
                )}
              </div>
            ) : (
              <div className="whitespace-pre-wrap break-words">
                {msg.content}
                {streaming && msg === messages[messages.length - 1] && msg.role === "assistant" && (
                  <span className="inline-block w-2 h-4 bg-[var(--accent)] animate-pulse ml-1" />
                )}
              </div>
            )}

            {/* Footer: edit button (user only) */}
            {msg.role === "user" && onEdit && msg.content && (
              <div className="mt-2 flex justify-end">
                <button
                  onClick={() => onEdit(msg.content)}
                  className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-white/60 transition-colors hover:bg-white/10 hover:text-white"
                  title="编辑"
                >
                  <Pencil size={12} />
                  编辑
                </button>
              </div>
            )}

            {/* Footer: action buttons + timestamp (assistant only) */}
            {msg.role === "assistant" && msg.content && (
              <div className="mt-3 flex items-center justify-between border-t border-[var(--surface-border)] pt-2">
                <div className="flex items-center gap-0.5">
                  <CopyButton content={msg.content} />
                  {onRegenerate && (
                    <button
                      onClick={onRegenerate}
                      className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-alt)] hover:text-[var(--text-primary)]"
                      title="重新生成"
                    >
                      <RefreshCw size={12} />
                    </button>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() =>
                      setFeedback((prev) => ({
                        ...prev,
                        [msg.id]: prev[msg.id] === "like" ? undefined : "like",
                      }))
                    }
                    className={`rounded-md p-1 transition-colors ${
                      feedback[msg.id] === "like"
                        ? "text-[var(--accent)]"
                        : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                    }`}
                    title="赞"
                  >
                    <ThumbsUp size={12} />
                  </button>
                  <button
                    onClick={() =>
                      setFeedback((prev) => ({
                        ...prev,
                        [msg.id]: prev[msg.id] === "dislike" ? undefined : "dislike",
                      }))
                    }
                    className={`rounded-md p-1 transition-colors ${
                      feedback[msg.id] === "dislike"
                        ? "text-[var(--danger)]"
                        : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                    }`}
                    title="踩"
                  >
                    <ThumbsDown size={12} />
                  </button>
                  <span className="text-xs text-[var(--text-secondary)]">
                    {new Date(msg.created_at).toLocaleTimeString("zh-CN", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
              </div>
            )}
          </div>
          {msg.role === "user" && (
            <div className="mt-1 grid h-8 w-8 shrink-0 place-items-center rounded-md bg-[var(--accent)] text-white shadow-[var(--shadow-sm)]">
              <UserRound size={16} />
            </div>
          )}
        </div>
      ))}

      {streaming && messages.length > 0 && messages[messages.length - 1].role === "user" && (
        <div className="flex justify-start gap-3">
          <div className="mt-1 grid h-8 w-8 shrink-0 place-items-center rounded-md bg-[var(--surface-panel)] text-[var(--accent)] shadow-[var(--shadow-sm)]">
            <Bot size={17} />
          </div>
          <div className="rounded-lg border border-[var(--surface-border)] bg-[var(--surface-panel)] px-4 py-3 text-sm shadow-[var(--shadow-sm)]">
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
