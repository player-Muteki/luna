"use client";

import { useRouter } from "next/navigation";
import { MessageSquare } from "lucide-react";

export default function ChatNewPage() {
  const router = useRouter();

  const createSession = async () => {
    try {
      const res = await fetch("/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "新对话" }),
      });
      const data = await res.json();
      router.push(`/chat/${data.id}`);
    } catch (e) {
      console.error("Failed to create session", e);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center h-full p-8">
      <MessageSquare size={48} className="text-[var(--text-secondary)] mb-4" />
      <h2 className="text-xl font-semibold mb-2">开始问答</h2>
      <p className="text-[var(--text-secondary)] mb-6 text-center max-w-md">
        选择左侧已有的会话，或创建一个新会话开始提问。
        RAG 系统将从已索引的文档中检索相关信息并生成回答。
      </p>
      <button
        onClick={createSession}
        className="px-6 py-3 rounded-lg bg-[var(--accent)] text-white hover:opacity-90 transition-opacity"
      >
        新建会话
      </button>
    </div>
  );
}
