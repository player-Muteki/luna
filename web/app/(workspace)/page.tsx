"use client";

import { useEffect, useState } from "react";
import { Files, MessageSquare, Database, Layers3 } from "lucide-react";
import Link from "next/link";
import { getProjectInfo, type ProjectInfo } from "@/lib/api";

export default function WorkspaceHome() {
  const [info, setInfo] = useState<ProjectInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getProjectInfo()
      .then(setInfo)
      .catch(() => setLoading(false))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-full p-6 lg:p-8">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <header className="flex flex-col gap-2 border-b border-[var(--surface-border)] pb-6">
          <p className="text-sm font-medium text-[var(--accent)]">Lore</p>
          <h1 className="text-2xl font-semibold tracking-tight text-[var(--text-primary)]">
            工作目录知识库
          </h1>
          <p className="max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
            管理本地文件索引，并基于已索引内容进行上下文问答。
          </p>
        </header>

        {loading ? (
          <div className="rounded-lg border border-[var(--surface-border)] bg-[var(--surface-panel)] p-6 text-sm text-[var(--text-secondary)] shadow-[var(--shadow-sm)]">
            正在读取项目状态...
          </div>
        ) : info ? (
          <section className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
            <div className="rounded-lg border border-[var(--surface-border)] bg-[var(--surface-panel)] p-6 shadow-[var(--shadow-sm)]">
              <div className="mb-5 flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                    当前项目
                  </p>
                  <h2 className="mt-1 truncate text-lg font-semibold text-[var(--text-primary)]">
                    {info.name}
                  </h2>
                  <p className="mt-2 truncate font-mono text-xs text-[var(--text-secondary)]">
                    {info.root}
                  </p>
                </div>
                <div className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-[var(--accent-soft)] text-[var(--accent)]">
                  <Database size={19} />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-md border border-[var(--surface-border)] bg-[var(--surface-bg)] p-4">
                  <div className="text-2xl font-semibold">{info.stats?.indexed_count ?? 0}</div>
                  <div className="mt-1 text-xs text-[var(--text-secondary)]">已索引</div>
                </div>
                <div className="rounded-md border border-[var(--surface-border)] bg-[var(--surface-bg)] p-4">
                  <div className="text-2xl font-semibold">{info.stats?.document_count ?? 0}</div>
                  <div className="mt-1 text-xs text-[var(--text-secondary)]">文档</div>
                </div>
                <div className="rounded-md border border-[var(--surface-border)] bg-[var(--surface-bg)] p-4">
                  <div className="text-2xl font-semibold">{info.stats?.chunk_count ?? 0}</div>
                  <div className="mt-1 text-xs text-[var(--text-secondary)]">片段</div>
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-[var(--surface-border)] bg-[var(--surface-panel)] p-6 shadow-[var(--shadow-sm)]">
              <div className="mb-5 flex items-center gap-3">
                <div className="grid h-10 w-10 place-items-center rounded-md bg-[var(--success-soft)] text-[var(--success)]">
                  <Layers3 size={19} />
                </div>
                <div>
                  <h2 className="text-base font-semibold">下一步</h2>
                  <p className="text-sm text-[var(--text-secondary)]">
                    选择常用工作流
                  </p>
                </div>
              </div>
              <div className="grid gap-3">
                <Link
                  href="/files"
                  className="flex items-center justify-between rounded-md border border-[var(--surface-border)] px-4 py-3 text-sm font-medium transition-colors hover:border-[var(--surface-border-strong)] hover:bg-[var(--surface-alt)]"
                >
                  <span className="flex items-center gap-2">
                    <Files size={17} />
                    文件管理
                  </span>
                  <span className="text-xs text-[var(--text-muted)]">更新索引</span>
                </Link>
                <Link
                  href="/chat"
                  className="flex items-center justify-between rounded-md bg-[var(--accent)] px-4 py-3 text-sm font-medium text-white shadow-[var(--shadow-sm)] transition-colors hover:bg-[var(--accent-hover)]"
                >
                  <span className="flex items-center gap-2">
                    <MessageSquare size={17} />
                    开始问答
                  </span>
                  <span className="text-xs text-white/75">进入会话</span>
                </Link>
              </div>
            </div>
          </section>
        ) : null}
      </div>
    </div>
  );
}
