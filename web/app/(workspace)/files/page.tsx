"use client";

import { useState, useEffect, useCallback } from "react";
import FileTree from "@/components/files/FileTree";
import { RefreshCw, CheckSquare, Square, Search, Database, Trash2, RotateCw } from "lucide-react";
import { getFiles, ingestFiles, updateDocument, reindexDocument, clearAllIndex, deleteDocument, type FileItem } from "@/lib/api";

export default function FilesPage() {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [indexing, setIndexing] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [autoIndex, setAutoIndex] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem("lore-auto-index");
    if (stored !== null) {
      setAutoIndex(stored === "true");
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const loadFiles = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getFiles({ search: debouncedSearch || undefined });
      setFiles(data.files || []);
    } catch (e) {
      console.error("Failed to load files", e);
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch]);

  useEffect(() => {
    loadFiles();
  }, [loadFiles]);

  // 自动索引已移至 WorkspaceLayout 全局处理，进入文件页时仅刷新列表
  useEffect(() => {
    if (!loading) {
      window.dispatchEvent(new CustomEvent("index-updated"));
    }
  }, [loading]);

  const toggleFile = (path: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const toggleAll = () => {
    const filePaths = files.filter((f) => !f.is_dir).map((f) => f.path);
    if (selected.size === filePaths.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(filePaths));
    }
  };

  const handleIndex = async () => {
    if (selected.size === 0) return;
    setIndexing(true);
    try {
      await ingestFiles(Array.from(selected));
      await loadFiles();
      setSelected(new Set());
      window.dispatchEvent(new CustomEvent("index-updated"));
    } catch (e) {
      console.error("Index failed", e);
    } finally {
      setIndexing(false);
    }
  };

  const handleClearAll = async () => {
    if (!confirm("确定清空所有索引？此操作不可撤销。")) return;
    setClearing(true);
    try {
      await clearAllIndex();
      await loadFiles();
      setSelected(new Set());
      window.dispatchEvent(new CustomEvent("index-updated"));
    } catch (e) {
      console.error("Clear index failed", e);
    } finally {
      setClearing(false);
    }
  };

  const indexedCount = files.filter((f) => f.is_indexed).length;
  const totalFileCount = files.filter((f) => !f.is_dir).length;
  const allSelected = selected.size === totalFileCount && totalFileCount > 0;
  const someIndexed = indexedCount > 0;
  const selectedIndexedFiles = files.filter((f) => !f.is_dir && f.is_indexed && selected.has(f.path));
  const hasSelectedIndexed = selectedIndexedFiles.length > 0;

  const handleDeleteSelected = async () => {
    if (!hasSelectedIndexed) return;
    setDeleting(true);
    try {
      await Promise.all(
        selectedIndexedFiles.map((f) => deleteDocument(f.document_id))
      );
      await loadFiles();
      setSelected(new Set());
      window.dispatchEvent(new CustomEvent("index-updated"));
    } catch (e) {
      console.error("Delete selected index failed", e);
    } finally {
      setDeleting(false);
    }
  };

  const handleTagUpdate = async (documentId: string, tags: string[]) => {
    try {
      await updateDocument(documentId, { tags });
      setFiles((prev) =>
        prev.map((f) =>
          f.document_id === documentId ? { ...f, tags } : f
        )
      );
    } catch (e) {
      console.error("Tag update failed", e);
    }
  };

  const handleReindex = async () => {
    const toReindex = selectedIndexedFiles;
    if (toReindex.length === 0) return;
    setReindexing(true);
    try {
      await Promise.all(toReindex.map((f) => reindexDocument(f.document_id, f.path)));
      await loadFiles();
      setSelected(new Set());
      window.dispatchEvent(new CustomEvent("index-updated"));
    } catch (e) {
      console.error("Reindex failed", e);
    } finally {
      setReindexing(false);
    }
  };

  return (
    <div className="flex h-full flex-col p-6 lg:p-8">
      <header className="mb-5 flex flex-col gap-4 border-b border-[var(--surface-border)] pb-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-medium text-[var(--accent)]">Files</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">文件管理</h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            已索引 {indexedCount}/{totalFileCount} 个文件，用于后续问答检索。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleClearAll}
            disabled={clearing || !someIndexed}
            className="inline-flex h-10 items-center gap-2 rounded-md border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-3 text-sm font-medium text-[var(--danger)] shadow-[var(--shadow-sm)] transition-colors hover:bg-[var(--danger)] hover:text-white disabled:opacity-40"
            title="一键删除所有索引"
          >
            <Trash2 size={16} />
            一键删除索引
          </button>
          <button
            onClick={handleDeleteSelected}
            disabled={deleting || !hasSelectedIndexed}
            className="inline-flex h-10 items-center gap-2 rounded-md border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-3 text-sm font-medium text-[var(--danger)] shadow-[var(--shadow-sm)] transition-colors hover:bg-[var(--danger)] hover:text-white disabled:opacity-40"
            title="删除选中文件的索引"
          >
            <Trash2 size={16} />
            {deleting ? "删除中..." : `删除索引 ${selectedIndexedFiles.length || ""}`.trim()}
          </button>
          <button
            onClick={handleReindex}
            disabled={reindexing || !hasSelectedIndexed}
            className="inline-flex h-10 items-center gap-2 rounded-md border border-[var(--surface-border)] bg-[var(--surface-panel)] px-3 text-sm font-medium text-[var(--text-secondary)] shadow-[var(--shadow-sm)] transition-colors hover:bg-[var(--surface-alt)] disabled:opacity-50"
            title="重新索引选中文件"
          >
            <RotateCw size={16} className={reindexing ? "animate-spin" : ""} />
            {reindexing ? "重新索引中..." : "重新索引"}
          </button>
          <button
            onClick={loadFiles}
            disabled={loading || indexing || clearing || deleting}
            className="inline-flex h-10 items-center gap-2 rounded-md border border-[var(--surface-border)] bg-[var(--surface-panel)] px-3 text-sm font-medium text-[var(--text-secondary)] shadow-[var(--shadow-sm)] transition-colors hover:bg-[var(--surface-alt)] disabled:opacity-50"
          >
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
            刷新
          </button>
          <button
            onClick={handleIndex}
            disabled={selected.size === 0 || indexing}
            className="inline-flex h-10 items-center gap-2 rounded-md bg-[var(--accent)] px-4 text-sm font-medium text-white shadow-[var(--shadow-sm)] transition-colors hover:bg-[var(--accent-hover)] disabled:opacity-45"
          >
            <Database size={16} />
            {indexing ? "索引中..." : `索引 ${selected.size || ""}`.trim()}
          </button>
        </div>
      </header>

      <div className="mb-4 grid gap-3 lg:grid-cols-[1fr_auto]">
        <div className="relative">
          <Search
            size={16}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
          />
          <input
            type="text"
            placeholder="搜索文件..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-10 w-full rounded-md border border-[var(--surface-border)] bg-[var(--surface-panel)] pl-9 pr-3 text-sm shadow-[var(--shadow-sm)] outline-none transition-colors placeholder:text-[var(--text-muted)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-soft)]"
          />
        </div>
        <button
          onClick={toggleAll}
          disabled={totalFileCount === 0}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-[var(--surface-border)] bg-[var(--surface-panel)] px-3 text-sm font-medium text-[var(--text-secondary)] shadow-[var(--shadow-sm)] transition-colors hover:bg-[var(--surface-alt)] disabled:opacity-50"
        >
          {allSelected ? <CheckSquare size={16} /> : <Square size={16} />}
          {allSelected ? "取消全选" : "全选文件"}
        </button>
      </div>

      {selected.size > 0 && (
        <div className="mb-4 rounded-lg border border-[var(--surface-border)] bg-[var(--surface-panel)] p-3 text-sm shadow-[var(--shadow-sm)]">
          <div className="mb-2 flex items-center justify-between gap-3">
            <div className="font-medium">已选 {selected.size} 个文件</div>
            <button
              onClick={() => setSelected(new Set())}
              className="text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            >
              清空
            </button>
          </div>
          <div className="grid max-h-24 gap-1 overflow-y-auto">
            {Array.from(selected).slice(0, 10).map((p) => (
              <div
                key={p}
                className="truncate rounded bg-[var(--surface-bg)] px-2 py-1 font-mono text-xs text-[var(--text-secondary)]"
              >
                {p}
              </div>
            ))}
            {selected.size > 10 && (
              <div className="px-2 text-xs text-[var(--text-secondary)]">
                还有 {selected.size - 10} 个
              </div>
            )}
          </div>
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-auto rounded-lg border border-[var(--surface-border)] bg-[var(--surface-panel)] shadow-[var(--shadow-sm)]">
        {loading ? (
          <div className="flex h-full min-h-64 items-center justify-center text-sm text-[var(--text-secondary)]">
            正在加载文件...
          </div>
        ) : files.length === 0 ? (
          <div className="flex h-full min-h-64 items-center justify-center p-8 text-center">
            <div>
              <FilesEmptyIcon />
              <p className="mt-3 text-sm font-medium">没有找到文件</p>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                调整搜索条件或刷新文件列表。
              </p>
            </div>
          </div>
        ) : (
          <FileTree files={files} selected={selected} onToggle={toggleFile} onTagUpdate={handleTagUpdate} />
        )}
      </div>
    </div>
  );
}

function FilesEmptyIcon() {
  return (
    <div className="mx-auto grid h-12 w-12 place-items-center rounded-lg bg-[var(--surface-alt)] text-[var(--text-muted)]">
      <Search size={22} />
    </div>
  );
}
