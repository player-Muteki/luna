"use client";

import { useEffect, useState } from "react";
import { Files, MessageSquare } from "lucide-react";
import Link from "next/link";

interface ProjectInfo {
  root: string;
  name: string;
  config: Record<string, unknown>;
  stats: {
    document_count?: number;
    indexed_count?: number;
    chunk_count?: number;
  };
}

export default function WorkspaceHome() {
  const [info, setInfo] = useState<ProjectInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/project")
      .then((res) => res.json())
      .then((data) => {
        setInfo(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  return (
    <div className="flex flex-col items-center justify-center h-full p-8 text-center">
      <div className="max-w-lg">
        <h1 className="text-3xl font-bold mb-2">Co-Thinker</h1>
        <p className="text-[var(--text-secondary)] mb-8">
          基于 RAG 的工作目录知识库系统
        </p>

        {loading ? (
          <div className="text-[var(--text-secondary)]">加载中...</div>
        ) : info ? (
          <div className="bg-[var(--surface-alt)] rounded-lg p-6 mb-8 text-left">
            <div className="mb-4">
              <span className="text-sm text-[var(--text-secondary)]">项目</span>
              <div className="font-mono text-sm truncate">{info.root}</div>
            </div>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <div className="text-2xl font-bold">{info.stats?.indexed_count ?? 0}</div>
                <div className="text-xs text-[var(--text-secondary)]">已索引</div>
              </div>
              <div>
                <div className="text-2xl font-bold">{info.stats?.document_count ?? 0}</div>
                <div className="text-xs text-[var(--text-secondary)]">文档</div>
              </div>
              <div>
                <div className="text-2xl font-bold">{info.stats?.chunk_count ?? 0}</div>
                <div className="text-xs text-[var(--text-secondary)]">片段</div>
              </div>
            </div>
          </div>
        ) : null}

        <div className="flex gap-4 justify-center">
          <Link
            href="/files"
            className="flex items-center gap-2 px-6 py-3 rounded-lg bg-[var(--accent)] text-white hover:opacity-90 transition-opacity"
          >
            <Files size={18} />
            文件管理
          </Link>
          <Link
            href="/chat"
            className="flex items-center gap-2 px-6 py-3 rounded-lg border border-[var(--surface-border)] hover:bg-[var(--surface-alt)] transition-colors"
          >
            <MessageSquare size={18} />
            开始问答
          </Link>
        </div>
      </div>
    </div>
  );
}
