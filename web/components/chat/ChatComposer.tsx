"use client";

import { useState, useRef, KeyboardEvent } from "react";
import { Send } from "lucide-react";

export default function ChatComposer({
  onSend,
  disabled,
  placeholder,
}: {
  onSend: (content: string) => void;
  disabled: boolean;
  placeholder: string;
}) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  };

  return (
    <div className="border-t border-[var(--surface-border)] bg-[var(--surface-panel)] p-4">
      <div className="flex items-end gap-2 max-w-4xl mx-auto">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none rounded-lg border border-[var(--surface-border)] bg-[var(--surface-bg)] px-4 py-3 text-sm leading-6 shadow-[var(--shadow-sm)] outline-none transition-colors placeholder:text-[var(--text-muted)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-soft)] disabled:opacity-50 min-h-[44px] max-h-[200px]"
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || disabled}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-[var(--accent)] text-white shadow-[var(--shadow-sm)] transition-colors hover:bg-[var(--accent-hover)] disabled:opacity-35"
          title="发送"
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  );
}
