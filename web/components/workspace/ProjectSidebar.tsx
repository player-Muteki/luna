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
  Database,
} from "lucide-react";
import { getProjectInfo, sessions as sessionsApi, type ProjectInfo } from "@/lib/api";

interface Session {
  id: string;
  title: string;
  message_count: number;
  is_current: boolean;
  updated_at: string;
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

  // Fetch project info and sessions on mount only — index-updated event
  // handles refreshes after indexing operations.
  useEffect(() => {
    getProjectInfo().then(setInfo).catch(() => {});
  }, []);

  useEffect(() => {
    sessionsApi.list().then((d) => setSessions(d.sessions)).catch(() => {});
  }, []);

  // 监听索引更新事件，自动刷新统计
  useEffect(() => {
    const handler = () => {
      getProjectInfo().then(setInfo).catch(() => {});
    };
    window.addEventListener("index-updated", handler);
    return () => window.removeEventListener("index-updated", handler);
  }, []);

  const createSession = async () => {
    try {
      const data = await sessionsApi.create();
      router.push(`/chat/${data.id}`);
    } catch (e) {
      console.error(e);
    }
  };

  const deleteSession = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await sessionsApi.delete(id);
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

  const navItemClass =
    "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors";
  const inactiveNavClass =
    "text-[var(--sidebar-muted)] hover:bg-[var(--sidebar-hover)] hover:text-[var(--sidebar-fg)]";

  return (
    <aside
      className={`flex shrink-0 flex-col border-r border-[var(--surface-border)] bg-[var(--sidebar-bg)] text-[var(--sidebar-fg)] shadow-sm transition-all duration-200 ${
        collapsed ? "w-14" : "w-72"
      }`}
    >
      <div className="flex h-14 items-center justify-between border-b border-[var(--sidebar-divider)] px-3">
        {!collapsed && (
          <Link href="/chat" className="min-w-0">
            <div className="truncate text-sm font-semibold tracking-wide">
              {info?.name || "Co-Thinker"}
            </div>
            <div className="mt-0.5 text-xs text-[var(--sidebar-muted)]">
              本地知识工作区
            </div>
          </Link>
        )}
        <button
          onClick={onToggle}
          className="grid h-8 w-8 place-items-center rounded-md text-[var(--sidebar-muted)] transition-colors hover:bg-[var(--sidebar-hover)] hover:text-[var(--sidebar-fg)]"
          title={collapsed ? "展开侧边栏" : "收起侧边栏"}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      {collapsed ? (
        <nav className="flex flex-col gap-2 p-2">
          <Link
            href="/files"
            title="文件管理"
            className={`grid h-10 w-10 place-items-center rounded-md transition-colors ${
              pathname.includes("/files")
                ? "bg-[var(--sidebar-active)] text-[var(--sidebar-fg)]"
                : inactiveNavClass
            }`}
          >
            <Files size={18} />
          </Link>
          <Link
            href="/chat"
            title="问答"
            className={`grid h-10 w-10 place-items-center rounded-md transition-colors ${
              pathname.includes("/chat")
                ? "bg-[var(--sidebar-active)] text-[var(--sidebar-fg)]"
                : inactiveNavClass
            }`}
          >
            <MessageSquare size={18} />
          </Link>
          <button
            onClick={createSession}
            title="新建会话"
            className="grid h-10 w-10 place-items-center rounded-md text-[var(--sidebar-muted)] transition-colors hover:bg-[var(--sidebar-hover)] hover:text-[var(--sidebar-fg)]"
          >
            <Plus size={18} />
          </button>
        </nav>
      ) : (
        <>
          {info && (
            <div className="border-b border-[var(--sidebar-divider)] px-3 py-3">
              <div className="flex items-center gap-2 rounded-md bg-[var(--sidebar-active)] px-3 py-2">
                <Database size={16} className="text-[var(--accent)]" />
                <div className="min-w-0">
                  <div className="text-xs font-medium text-[var(--sidebar-fg)]">
                    {info.stats?.indexed_count ?? 0} 个文件已索引
                  </div>
                  <div className="text-xs text-[var(--sidebar-muted)]">
                    {info.stats?.chunk_count ?? 0} 个检索片段
                  </div>
                </div>
              </div>
            </div>
          )}

            <nav className="space-y-1 border-b border-[var(--sidebar-divider)] p-2">
            <Link
              href="/files"
              className={`${navItemClass} ${
                pathname.includes("/files")
                  ? "bg-[var(--sidebar-active)] text-[var(--sidebar-fg)]"
                  : inactiveNavClass
              }`}
            >
              <Files size={16} />
              <span>文件管理</span>
            </Link>
            <Link
              href="/chat"
              className={`${navItemClass} ${
                pathname.includes("/chat")
                  ? "bg-[var(--sidebar-active)] text-[var(--sidebar-fg)]"
                  : inactiveNavClass
              }`}
            >
              <MessageSquare size={16} />
              <span>问答</span>
            </Link>
          </nav>

          <div className="flex-1 overflow-auto p-2">
            <div className="flex items-center justify-between px-2 py-2 text-xs font-semibold uppercase tracking-wide text-[var(--sidebar-muted)]">
              <span>会话</span>
              <button
                onClick={createSession}
                className="grid h-7 w-7 place-items-center rounded-md transition-colors hover:bg-[var(--sidebar-hover)] hover:text-[var(--sidebar-fg)]"
                title="新建会话"
              >
                <Plus size={15} />
              </button>
            </div>
            <div className="mt-1 space-y-1">
              {sessions.map((s) => (
                <Link
                  key={s.id}
                  href={`/chat/${s.id}`}
                  className={`group flex items-center justify-between gap-2 rounded-md px-3 py-2 text-sm transition-colors ${
                    pathname.includes(s.id)
                      ? "bg-[var(--sidebar-active)] text-[var(--sidebar-fg)]"
                      : "text-[var(--sidebar-muted)] hover:bg-[var(--sidebar-hover)] hover:text-[var(--sidebar-fg)]"
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="truncate font-medium">{s.title}</div>
                    <div className="text-xs text-[var(--sidebar-muted)]">
                      {s.message_count} 条消息 · {formatDate(s.updated_at)}
                    </div>
                  </div>
                  <button
                    onClick={(e) => deleteSession(s.id, e)}
                    className="grid h-7 w-7 shrink-0 place-items-center rounded-md text-[var(--danger)] opacity-0 transition-opacity hover:bg-white/10 group-hover:opacity-100"
                    title="删除会话"
                  >
                    <Trash2 size={13} />
                  </button>
                </Link>
              ))}
              {sessions.length === 0 && (
                <div className="rounded-md border border-[var(--sidebar-divider)] px-3 py-4 text-sm text-[var(--sidebar-muted)]">
                  暂无会话
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </aside>
  );
}
