/**
 * API 客户端封装 — 与 Co-Thinker FastAPI 后端通信。
 */

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

  return res.json();
}

/** 获取项目信息 */
export function getProjectInfo() {
  return request<{
    root: string;
    name: string;
    config: Record<string, unknown>;
    stats: {
      document_count: number;
      indexed_count: number;
      chunk_count: number;
    };
  }>("/api/project");
}

/** 获取文件列表 */
export function getFiles(params?: { subdir?: string; search?: string }) {
  const searchParams = new URLSearchParams();
  if (params?.subdir) searchParams.set("subdir", params.subdir);
  if (params?.search) searchParams.set("search", params.search);
  const qs = searchParams.toString();
  return request<{ files: any[]; total: number }>(
    `/api/files${qs ? `?${qs}` : ""}`
  );
}

/** 索引文件 */
export function ingestFiles(paths: string[]) {
  return request<{
    total_files: number;
    indexed_files: number;
    total_chunks: number;
  }>("/api/ingest", {
    method: "POST",
    body: JSON.stringify({ paths }),
  });
}

/** 获取索引统计 */
export function getStats() {
  return request<{
    document_count: number;
    indexed_document_count: number;
    chunk_count: number;
  }>("/api/stats");
}

/** 会话相关 */
export const sessions = {
  list() {
    return request<{ sessions: any[] }>("/api/sessions");
  },
  get(id: string) {
    return request<{
      id: string;
      title: string;
      messages: any[];
    }>(`/api/sessions/${id}`);
  },
  create(title = "新对话") {
    return request<{ id: string; title: string }>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ title }),
    });
  },
  delete(id: string) {
    return request<{ status: string }>(`/api/sessions/${id}`, {
      method: "DELETE",
    });
  },
  rename(id: string, title: string) {
    return request<{ status: string; title: string }>(
      `/api/sessions/${id}`,
      {
        method: "PATCH",
        body: JSON.stringify({ title }),
      }
    );
  },
};
