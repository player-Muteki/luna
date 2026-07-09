"use client";

import { useRouter } from "next/navigation";
import { MessageSquare, Plus } from "lucide-react";
import { sessions } from "@/lib/api";

export default function ChatNewPage() {
  const router = useRouter();

  const createSession = async () => {
    try {
      const data = await sessions.create("新对话");
      router.push(`/chat/${data.id}`);
    } catch (e) {
      console.error("Failed to create session", e);
    }
  };

  return (
    <div className="flex h-full items-center justify-center p-6">
      <div className="max-w-md rounded-lg border border-[var(--surface-border)] bg-[var(--surface-panel)] p-8 text-center shadow-[var(--shadow-sm)]">
        <div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-lg bg-[var(--accent-soft)] text-[var(--accent)]">
          <MessageSquare size={24} />
        </div>
        <h1 className="text-xl font-semibold">开始问答</h1>
        <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
          选择左侧已有会话，或创建一个新会话后提问。
        </p>
        <button
          onClick={createSession}
          className="mt-6 inline-flex h-10 items-center gap-2 rounded-md bg-[var(--accent)] px-4 text-sm font-medium text-white shadow-[var(--shadow-sm)] transition-colors hover:bg-[var(--accent-hover)]"
        >
          <Plus size={16} />
          新建会话
        </button>
      </div>
    </div>
  );
}
