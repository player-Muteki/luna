"use client";

import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { Send, Check, ChevronDown } from "lucide-react";

const MODEL_KEY = "lore-model";

export interface SendOptions {
  model?: string;
}

export default function ChatComposer({
  onSend,
  disabled,
  placeholder,
  editValue,
}: {
  onSend: (content: string, options?: SendOptions) => void;
  disabled: boolean;
  placeholder: string;
  editValue?: string | null;
}) {
  const [input, setInput] = useState("");
  const [modelOpen, setModelOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState("deepseek-v4-flash");
  const [models, setModels] = useState<{ id: string; name: string }[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // 每次打开页面从设置读取全局默认模型
    const saved = localStorage.getItem(MODEL_KEY);
    if (saved) {
      setSelectedModel(saved);
    }
    fetch("/api/models")
      .then((r) => r.json())
      .then((data) => {
        if (data.models && data.models.length > 0) {
          setModels(data.models);
        }
      })
      .catch((e) => console.error("Failed to load models", e));
  }, []);

  useEffect(() => {
    if (!modelOpen) return;
    const handle = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setModelOpen(false);
      }
    };
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [modelOpen]);

  // Sync edit value from parent (e.g. "edit" button click)
  useEffect(() => {
    if (editValue !== undefined && editValue !== null) {
      setInput(editValue);
      textareaRef.current?.focus();
    }
  }, [editValue]);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed, { model: selectedModel });
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
    <form
      onSubmit={(e) => { e.preventDefault(); handleSend(); }}
      className="border-t border-[var(--surface-border)] bg-[var(--surface-panel)] p-4"
    >
      <div className="flex items-end gap-2 max-w-4xl mx-auto">
        {/* Model switcher */}
        <div className="relative shrink-0" ref={dropdownRef}>
          <button
            onClick={() => setModelOpen(!modelOpen)}
            disabled={disabled}
            className="flex h-11 items-center gap-1 rounded-lg border border-[var(--surface-border)] bg-[var(--surface-bg)] px-2.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:border-[var(--accent)] hover:text-[var(--accent)] disabled:opacity-50"
            title="切换模型"
          >
            {selectedModel.length > 18 ? selectedModel.slice(0, 16) + "…" : selectedModel}
            <ChevronDown size={12} className={`transition-transform ${modelOpen ? "rotate-180" : ""}`} />
          </button>
          {modelOpen && (
            <div className="absolute bottom-full left-0 mb-1 w-48 max-h-60 overflow-y-auto rounded-md border border-[var(--surface-border)] bg-[var(--surface-panel)] py-1 shadow-[var(--shadow-md)]">
              {models.length === 0 ? (
                <div className="px-3 py-2 text-xs text-[var(--text-muted)]">暂无可用模型</div>
              ) : (
                models.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => {
                      setSelectedModel(m.id);
                      setModelOpen(false);
                    }}
                    className={`flex w-full items-center justify-between px-3 py-2 text-xs transition-colors hover:bg-[var(--surface-alt)] ${
                      selectedModel === m.id ? "text-[var(--accent)]" : "text-[var(--text-primary)]"
                    }`}
                  >
                    <span className="truncate">{m.name}</span>
                    {selectedModel === m.id && <Check size={12} className="shrink-0" />}
                  </button>
                ))
              )}
            </div>
          )}
        </div>

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
    </form>
  );
}
