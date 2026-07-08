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
    <div className="border-t border-[var(--surface-border)] p-4">
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
          className="flex-1 px-4 py-3 rounded-lg border border-[var(--surface-border)] bg-[var(--surface-bg)] resize-none focus:outline-none focus:border-[var(--accent)] text-sm disabled:opacity-50"
          style={{ minHeight: "44px", maxHeight: "200px" }}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || disabled}
          className="flex items-center justify-center w-11 h-11 rounded-lg bg-[var(--accent)] text-white hover:opacity-90 disabled:opacity-30 transition-opacity shrink-0"
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  );
}
