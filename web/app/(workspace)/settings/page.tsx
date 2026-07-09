"use client";

import { useState, useEffect, useRef } from "react";
import { Eye, EyeOff, Check } from "lucide-react";

const AUTO_INDEX_KEY = "co-thinker-auto-index";
const MODEL_KEY = "co-thinker-model";

export default function SettingsPage() {
  const [autoIndex, setAutoIndex] = useState(true);
  const [apiKey, setApiKey] = useState("");
  const [selectedModel, setSelectedModel] = useState("deepseek-v4-flash");
  const [models, setModels] = useState<{ id: string; name: string }[]>([]);
  const [topK, setTopK] = useState(5);
  const [chunkSize, setChunkSize] = useState(800);
  const [showApiKey, setShowApiKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [modelOpen, setModelOpen] = useState(false);
  const modelRef = useRef<HTMLDivElement>(null);

  // Load saved settings and available models on mount
  useEffect(() => {
    const stored = localStorage.getItem(AUTO_INDEX_KEY);
    if (stored !== null) {
      setAutoIndex(stored === "true");
    }
    const savedModel = localStorage.getItem(MODEL_KEY);
    if (savedModel) {
      setSelectedModel(savedModel);
    }
    fetch("/api/config")
      .then((r) => r.json())
      .then((data) => {
        setTopK(data.top_k ?? 5);
        setChunkSize(data.chunk_size ?? 800);
      })
      .catch(() => {});
    fetchModels();
  }, []);

  const fetchModels = async () => {
    try {
      const res = await fetch("/api/models");
      const data = await res.json();
      if (data.models && data.models.length > 0) {
        setModels(data.models);
      }
    } catch {
      // silent
    }
  };

  // Close model dropdown on outside click
  useEffect(() => {
    if (!modelOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (modelRef.current && !modelRef.current.contains(e.target as Node)) {
        setModelOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [modelOpen]);

  // Auto-save: debounced save when any setting changes
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const saveSettings = () => {
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    saveTimeoutRef.current = setTimeout(async () => {
      setSaving(true);
      try {
        localStorage.setItem(AUTO_INDEX_KEY, String(autoIndex));
        localStorage.setItem(MODEL_KEY, selectedModel);

        const body: Record<string, unknown> = {
          top_k: topK,
          chunk_size: chunkSize,
          model: selectedModel,
        };
        if (apiKey) body.api_key = apiKey;
        const res = await fetch("/api/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (res.ok) {
          setApiKey("");
          fetchModels();
        }
      } catch {
        // silent
      } finally {
        setSaving(false);
      }
    }, 600);
  };

  // Watch all settings for auto-save
  useEffect(() => {
    saveSettings();
    return () => {
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    };
  }, [autoIndex, selectedModel, topK, chunkSize]);

  return (
    <div className="mx-auto max-w-xl p-6 lg:p-8">
      <header className="mb-6 border-b border-[var(--surface-border)] pb-5">
        <p className="text-sm font-medium text-[var(--accent)]">Settings</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">设置</h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          管理应用程序配置和检索参数（自动保存）。
          {saving && <span className="ml-2 text-[var(--text-muted)]">保存中...</span>}
        </p>
      </header>

      <div className="space-y-6">
        {/* Auto-index toggle */}
        <div className="rounded-lg border border-[var(--surface-border)] bg-[var(--surface-panel)] p-4 shadow-[var(--shadow-sm)]">
          <label className="flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-[var(--text-primary)]">打开时一键索引</div>
              <div className="mt-0.5 text-xs text-[var(--text-secondary)]">
                开启后每次进入文件管理页面时自动索引未索引的文件
              </div>
            </div>
            <button
              onClick={() => setAutoIndex(!autoIndex)}
              className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
                autoIndex ? "bg-[var(--accent)]" : "bg-[var(--surface-border)]"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform ${
                  autoIndex ? "translate-x-4" : "translate-x-0"
                }`}
              />
            </button>
          </label>
        </div>

        {/* Model selector */}
        <div className="rounded-lg border border-[var(--surface-border)] bg-[var(--surface-panel)] p-4 shadow-[var(--shadow-sm)]">
          <h2 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">模型</h2>
          <div className="relative" ref={modelRef}>
            <button
              onClick={() => setModelOpen(!modelOpen)}
              className="flex h-9 w-full items-center justify-between rounded-md border border-[var(--surface-border)] bg-[var(--surface-bg)] px-3 text-sm outline-none transition-colors hover:border-[var(--accent)]"
            >
              <span>{selectedModel}</span>
              <svg
                className={`h-4 w-4 text-[var(--text-muted)] transition-transform ${modelOpen ? "rotate-180" : ""}`}
                viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
              >
                <path d="m6 9 6 6 6-6" />
              </svg>
            </button>
            {modelOpen && (
              <div className="absolute left-0 right-0 top-full z-10 mt-1 max-h-60 overflow-y-auto rounded-md border border-[var(--surface-border)] bg-[var(--surface-panel)] py-1 shadow-[var(--shadow-md)]">
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
                      className={`flex w-full items-center justify-between px-3 py-2 text-sm transition-colors hover:bg-[var(--surface-alt)] ${
                        selectedModel === m.id ? "text-[var(--accent)]" : "text-[var(--text-primary)]"
                      }`}
                    >
                      <span>{m.name}</span>
                      {selectedModel === m.id && <Check size={14} />}
                    </button>
                  ))
                )}
              </div>
            )}
          </div>
        </div>

        {/* API Key */}
        <div className="rounded-lg border border-[var(--surface-border)] bg-[var(--surface-panel)] p-4 shadow-[var(--shadow-sm)]">
          <h2 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">API Key</h2>
          <div className="relative">
            <input
              type={showApiKey ? "text" : "password"}
              value={apiKey}
              onChange={(e) => {
                setApiKey(e.target.value);
                saveSettings();
              }}
              placeholder="sk-...（留空则沿用已有配置）"
              className="h-9 w-full rounded-md border border-[var(--surface-border)] bg-[var(--surface-bg)] pr-8 pl-3 text-sm outline-none transition-colors placeholder:text-[var(--text-muted)] focus:border-[var(--accent)]"
            />
            <button
              onClick={() => setShowApiKey(!showApiKey)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            >
              {showApiKey ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          </div>
        </div>

        {/* Sliders */}
        <div className="rounded-lg border border-[var(--surface-border)] bg-[var(--surface-panel)] p-4 shadow-[var(--shadow-sm)]">
          <h2 className="mb-4 text-sm font-semibold text-[var(--text-primary)]">检索参数</h2>
          <div className="space-y-5">
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm text-[var(--text-secondary)]">Top K</label>
                <span className="text-sm font-medium text-[var(--text-primary)]">{topK}</span>
              </div>
              <input
                type="range"
                min={1}
                max={20}
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
                style={{
                  background: `linear-gradient(to right, var(--accent) ${((topK - 1) / 19) * 100}%, var(--surface-border) ${((topK - 1) / 19) * 100}%)`,
                }}
              />
              <div className="mt-1 flex justify-between text-xs text-[var(--text-muted)]">
                <span>1</span>
                <span>20</span>
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm text-[var(--text-secondary)]">Chunk Size</label>
                <span className="text-sm font-medium text-[var(--text-primary)]">{chunkSize}</span>
              </div>
              <input
                type="range"
                min={200}
                max={2000}
                step={100}
                value={chunkSize}
                onChange={(e) => setChunkSize(Number(e.target.value))}
                className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
                style={{
                  background: `linear-gradient(to right, var(--accent) ${((chunkSize - 200) / 1800) * 100}%, var(--surface-border) ${((chunkSize - 200) / 1800) * 100}%)`,
                }}
              />
              <div className="mt-1 flex justify-between text-xs text-[var(--text-muted)]">
                <span>200</span>
                <span>2000</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
