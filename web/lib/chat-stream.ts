/**
 * ChatStream — WebSocket 流式对话的封装。
 *
 * 页面只订阅高层事件回调，不再直接处理 WebSocket 原始协议。
 *
 * 用法：
 * ```ts
 * const stream = new ChatStream(sessionId, {
 *   onChunk: (text) => appendAssistantContent(text),
 *   onRetrievalDone: (details) => setRetrievalDetails(details),
 *   onDone: () => reloadSession(),
 *   onError: (msg) => showError(msg),
 *   onStatusChange: (status) => setConnectionStatus(status),
 * });
 * stream.connect();
 * stream.sendQuery("问题");
 * ```
 */

// ── 类型 ─────────────────────────────────────────────────────────

export type ConnectionStatus = "connecting" | "connected" | "disconnected";

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

export interface ChatStreamCallbacks {
  /** 逐块追加的答案文本 */
  onChunk?: (content: string) => void;
  /** 推理过程文本片段 */
  onReasoning?: (content: string) => void;
  /** 检索完成通知 */
  onRetrievalDone?: (details: RetrievalDetails) => void;
  /** 流式生成完成 */
  onDone?: (sessionId: string, references: unknown[], confidence: string) => void;
  /** 错误消息 */
  onError?: (message: string) => void;
  /** 连接状态变化 */
  onStatusChange?: (status: ConnectionStatus) => void;
}

// ── ChatStream class ─────────────────────────────────────────────

export class ChatStream {
  private ws: WebSocket | null = null;
  private callbacks: ChatStreamCallbacks;
  private sessionId: string;
  private intentionalClose = false;

  constructor(sessionId: string, callbacks: ChatStreamCallbacks) {
    this.sessionId = sessionId;
    this.callbacks = callbacks;
  }

  /** 建立 WebSocket 连接。 */
  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;
    this.intentionalClose = false;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const envUrl = typeof process !== "undefined" ? process.env.NEXT_PUBLIC_WS_URL || null : null;
    const url = envUrl || `${protocol}//${host}/api/ws/chat`;

    this.callbacks.onStatusChange?.("connecting");

    const socket = new WebSocket(url);
    socket.onopen = () => {
      this.ws = socket;
      this.callbacks.onStatusChange?.("connected");
    };
    socket.onmessage = (event: MessageEvent) => this.handleMessage(event);
    socket.onclose = () => {
      this.ws = null;
      if (!this.intentionalClose) {
        this.callbacks.onStatusChange?.("disconnected");
      }
    };
    socket.onerror = () => {
      this.ws = null;
      if (!this.intentionalClose) {
        this.callbacks.onStatusChange?.("disconnected");
      }
    };
  }

  /** 发送一条用户查询。 */
  sendQuery(content: string, model?: string, options?: { deepthink?: boolean; search?: boolean }): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.callbacks.onError?.("WebSocket 未连接");
      return;
    }
    const payload: Record<string, unknown> = {
      type: "query",
      content,
      session_id: this.sessionId,
    };
    if (model) payload.model = model;
    if (options?.deepthink) payload.deepthink = true;
    if (options?.search) payload.search = true;
    this.ws.send(JSON.stringify(payload));
  }

  /** 主动断开连接。 */
  disconnect(): void {
    this.intentionalClose = true;
    this.ws?.close();
    this.ws = null;
    this.callbacks.onStatusChange?.("disconnected");
  }

  // ── 内部 ──

  private handleMessage(event: MessageEvent): void {
    let msg: Record<string, unknown>;
    try {
      msg = JSON.parse(event.data as string);
    } catch {
      console.error("ChatStream: invalid JSON from server", event.data);
      return;
    }

    const type = msg.type as string | undefined;

    switch (type) {
      case "chunk":
        this.callbacks.onChunk?.(msg.content as string);
        break;

      case "reasoning":
        this.callbacks.onReasoning?.(msg.content as string);
        break;

      case "retrieval_done": {
        const { type: _t, ...details } = msg;
        this.callbacks.onRetrievalDone?.(details as unknown as RetrievalDetails);
        break;
      }

      case "done":
        this.callbacks.onDone?.(
          msg.session_id as string,
          msg.references as unknown[],
          msg.confidence as string
        );
        break;

      case "error":
        this.callbacks.onError?.(msg.message as string);
        break;

      default:
        console.warn("ChatStream: unknown message type", type);
    }
  }
}
