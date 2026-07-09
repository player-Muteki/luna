/**
 * API 客户端 — 与 Co-Thinker FastAPI 后端通信。
 *
 * 所有 HTTP 请求集中在此 module。页面只调用这些方法，
 * 不直接拼 URL、不直接 fetch。
 */

// ── 类型 ─────────────────────────────────────────────────────────

export interface ProjectInfo {
  root: string;
  name: string;
  config: Record<string, unknown>;
  stats: {
    document_count: number;
    indexed_count: number;
    chunk_count: number;
  };
}

export interface FileItem {
  path: string;
  name: string;
  ext: string;
  size: number;
  mtime: number;
  is_dir: boolean;
  is_indexed: boolean;
  document_id: string;
}

export interface FileListResponse {
  files: FileItem[];
  total: number;
}

export interface IngestResponse {
  total_files: number;
  indexed_files: number;
  skipped_files: number;
  failed_files: number;
  total_chunks: number;
  elapsed_ms: number;
  results: Array<{
    path: string;
    status: string;
    document_id: string;
    chunk_count: number;
    error?: string;
  }>;
}

export interface StatsResponse {
  document_count: number;
  indexed_document_count: number;
  chunk_count: number;
}

export interface SessionSummary {
  id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
  is_current: boolean;
  last_message_preview: string;
}

export interface MessageData {
  id: string;
  role: string;
  content: string;
  created_at: string;
  metadata?: Record<string, unknown>;
}

export interface SessionDetail {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: MessageData[];
}

export interface SessionListResponse {
  sessions: SessionSummary[];
}

// ── HTTP client ──────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }

  return res.json() as Promise<T>;
}

// ── Project ──────────────────────────────────────────────────────

/** 获取项目信息 */
export function getProjectInfo(): Promise<ProjectInfo> {
  return request<ProjectInfo>("/api/project");
}

/** 获取索引统计 */
export function getStats(): Promise<StatsResponse> {
  return request<StatsResponse>("/api/stats");
}

// ── Files ────────────────────────────────────────────────────────

/** 获取文件列表 */
export function getFiles(params?: {
  subdir?: string;
  search?: string;
}): Promise<FileListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.subdir) searchParams.set("subdir", params.subdir);
  if (params?.search) searchParams.set("search", params.search);
  const qs = searchParams.toString();
  return request<FileListResponse>(`/api/files${qs ? `?${qs}` : ""}`);
}

// ── Ingest ───────────────────────────────────────────────────────

/** 索引指定文件 */
export function ingestFiles(paths: string[]): Promise<IngestResponse> {
  return request<IngestResponse>("/api/ingest", {
    method: "POST",
    body: JSON.stringify({ paths }),
  });
}

/** 扫描并增量重建索引 */
export function scanAndIndex(): Promise<IngestResponse> {
  return request<IngestResponse>("/api/ingest/scan", {
    method: "POST",
  });
}

/** 强制全量重建索引 */
export function rebuildIndex(): Promise<IngestResponse> {
  return request<IngestResponse>("/api/ingest/rebuild", {
    method: "POST",
  });
}

/** 删除指定文档的索引 */
export function deleteDocument(
  documentId: string
): Promise<{ status: string; path: string; chunk_count: number }> {
  return request(`/api/ingest/${documentId}`, {
    method: "DELETE",
  });
}

// ── Sessions ─────────────────────────────────────────────────────

export const sessions = {
  /** 获取会话列表 */
  list(): Promise<SessionListResponse> {
    return request<SessionListResponse>("/api/sessions");
  },

  /** 获取单个会话详情（含消息列表） */
  get(id: string): Promise<SessionDetail> {
    return request<SessionDetail>(`/api/sessions/${id}`);
  },

  /** 创建新会话 */
  create(title = "新对话"): Promise<{ id: string; title: string }> {
    return request<{ id: string; title: string }>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ title }),
    });
  },

  /** 删除会话 */
  delete(id: string): Promise<{ status: string }> {
    return request<{ status: string }>(`/api/sessions/${id}`, {
      method: "DELETE",
    });
  },

  /** 重命名会话 */
  rename(
    id: string,
    title: string
  ): Promise<{ status: string; title: string }> {
    return request<{ status: string; title: string }>(
      `/api/sessions/${id}`,
      {
        method: "PATCH",
        body: JSON.stringify({ title }),
      }
    );
  },
};
