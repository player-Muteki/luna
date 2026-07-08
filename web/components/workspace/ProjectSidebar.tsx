"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Files,
  MessageSquare,
  Plus,
  ChevronLeft,
  ChevronRight,
  Trash2,
} from "lucide-react";

interface Session {
  id: string;
  title: string;
  message_count: number;
  is_current: boolean;
  updated_at: string;
}

interface ProjectInfo {
  name: string;
  stats: { indexed_count?: number; chunk_count?: number };
}

export default function ProjectSidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  const [info, setInfo] = useState<ProjectInfo | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    fetch("/api/project")
      .then((r) => r.json())
      .then(setInfo)
      .catch(() => {});

    fetch("/api/sessions")
      .then((r) => r.json())
      .then((d) => setSessions(d.sessions || []))
      .catch(() => {});
  }, [pathname]);

  const createSession = async () => {
    try {
      const res = await fetch("/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data = await res.json();
      router.push(`/chat/${data.id}`);
    } catch (e) {
      console.error(e);
    }
  };

  const deleteSession = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await fetch(`/api/sessions/${id}`, { method: "DELETE" });
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (pathname.includes(id)) {
        router.push("/chat");
      }
    } catch (e) {
      console.error(e);
    }
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
  };

  return (
    <aside
      className={`flex flex-col bg-[var(--sidebar-bg)] text-[var(--sidebar-fg)] transition-all duration-200 ${
        collapsed ? "w-12" : "w-64"
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 h-12 border-b border-[var(--sidebar-active)]">
        {!collapsed && (
          <span className="font-semibold truncate text-sm">
            {info?.name || "Co-Thinker"}
          </span>
        )}
        <button
          onClick={onToggle}
          className="p-1 rounded hover:bg-[var(--sidebar-hover)] text-[var(--sidebar-muted)]"
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      {!collapsed && (
        <>
          {/* Project info */}
          {info && (
            <div className="px-3 py-2 text-xs text-[var(--sidebar-muted)] border-b border-[var(--sidebar-active)]">
              已索引 {info.stats?.indexed_count ?? 0} / {info.stats?.chunk_count ?? 0} 片段
            </div>
          )}

          {/* Navigation */}
          <nav className="p-2 space-y-1">
            <Link
              href="/files"
              className={`flex items-center gap-2 px-3 py-2 rounded text-sm ${
                pathname.includes("/files")
                  ? "bg-[var(--sidebar-active)] text-[var(--sidebar-fg)]"
                  : "text-[var(--sidebar-muted)] hover:bg-[var(--sidebar-hover)] hover:text-[var(--sidebar-fg)]"
              }`}
            >
              <Files size={16} />
              <span>文件管理</span>
            </Link>
            <Link
              href="/chat"
              className={`flex items-center gap-2 px-3 py-2 rounded text-sm ${
                pathname.includes("/chat")
                  ? "bg-[var(--sidebar-active)] text-[var(--sidebar-fg)]"
                  : "text-[var(--sidebar-muted)] hover:bg-[var(--sidebar-hover)] hover:text-[var(--sidebar-fg)]"
              }`}
            >
              <MessageSquare size={16} />
              <span>问答</span>
            </Link>
          </nav>

          {/* Sessions */}
          <div className="flex-1 overflow-auto p-2">
            <div className="flex items-center justify-between px-2 py-1 text-xs text-[var(--sidebar-muted)]">
              <span>会话</span>
              <button
                onClick={createSession}
                className="p-1 rounded hover:bg-[var(--sidebar-hover)]"
                title="新建会话"
              >
                <Plus size={14} />
              </button>
            </div>
            <div className="space-y-0.5 mt-1">
              {sessions.map((s) => (
                <Link
                  key={s.id}
                  href={`/chat/${s.id}`}
                  className={`group flex items-center justify-between px-3 py-2 rounded text-sm ${
                    pathname.includes(s.id)
                      ? "bg-[var(--sidebar-active)]"
                      : "hover:bg-[var(--sidebar-hover)]"
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="truncate">{s.title}</div>
                    <div className="text-xs text-[var(--sidebar-muted)]">
                      {s.message_count} 条消息 · {formatDate(s.updated_at)}
                    </div>
                  </div>
                  <button
                    onClick={(e) => deleteSession(s.id, e)}
                    className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-[var(--sidebar-active)] text-[var(--danger)]"
                    title="删除会话"
                  >
                    <Trash2 size={12} />
                  </button>
                </Link>
              ))}
            </div>
          </div>
        </>
      )}
    </aside>
  );
}
