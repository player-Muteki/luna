/**
 * WebSocket 客户端封装 — 流式问答。
 */

export interface ChatMessage {
  type: "chunk" | "done" | "error";
  content?: string;
  session_id?: string;
  references?: any[];
  confidence?: string;
  message?: string;
}

export type MessageHandler = (msg: ChatMessage) => void;

export class ChatWebSocket {
  private ws: WebSocket | null = null;
  private handlers: Set<MessageHandler> = new Set();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private shouldReconnect = true;

  connect(sessionId?: string) {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const url = `${protocol}//${host}/api/ws/chat`;

    this.shouldReconnect = true;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as ChatMessage;
        this.handlers.forEach((h) => h(msg));
      } catch (e) {
        console.error("WS parse error", e);
      }
    };

    this.ws.onclose = () => {
      if (this.shouldReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000);
        this.reconnectAttempts++;
        setTimeout(() => this.connect(), delay);
      }
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  disconnect() {
    this.shouldReconnect = false;
    this.ws?.close();
    this.ws = null;
  }

  sendQuery(content: string, sessionId?: string) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({
          type: "query",
          content,
          session_id: sessionId,
        })
      );
    }
  }

  onMessage(handler: MessageHandler) {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  get isConnected() {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

export function createChatWS() {
  return new ChatWebSocket();
}
