"use client";

import { useState, useEffect } from "react";
import { Settings, X, Eye, EyeOff } from "lucide-react";

const AUTO_INDEX_KEY = "co-thinker-auto-index";

export default function SettingsPanel() {
  const [open, setOpen] = useState(false);
  const [autoIndex, setAutoIndex] = useState(true);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [topK, setTopK] = useState(5);
  const [chunkSize, setChunkSize] = useState(800);
  const [showApiKey, setShowApiKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    const stored = localStorage.getItem(AUTO_INDEX_KEY);
    if (stored !== null) {
      setAutoIndex(stored === "true");
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    fetch("/api/config")
      .then((r) => r.json())
      .then((data) => {
        setTopK(data.top_k ?? 5);
        setChunkSize(data.chunk_size ?? 800);
        setBaseUrl(data.base_url ?? "");
      })
      .catch(() => {});
  }, [open]);

  const handleSave = async () => {
    setSaving(true);
    setMessage("");
    try {
      localStorage.setItem(AUTO_INDEX_KEY, String(autoIndex));

      const body: Record<string, unknown> = { top_k: topK, chunk_size: chunkSize };
      if (baseUrl) body.base_url = baseUrl;
      if (apiKey) body.api_key = apiKey;
      const res = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setMessage("保存成功");
        setApiKey("");
      } else {
        setMessage("保存失败");
      }
    } catch {
      setMessage("保存失败");
    } finally {
      setSaving(false);
      setTimeout(() => setMessage(""), 2000);
    }
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-4 left-4 z-40 grid h-10 w-10 place-items-center rounded-full bg-[var(--surface-panel)] text-[var(--text-secondary)] shadow-md border border-[var(--surface-border)] transition-colors hover:bg-[var(--surface-alt)] hover:text-[var(--text-primary)]"
        title="设置"
      >
        <Settings size={18} />
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="w-80 rounded-xl border border-[var(--surface-border)] bg-[var(--surface-panel)] shadow-[var(--shadow-md)]">
            <div className="flex items-center justify-between border-b border-[var(--surface-border)] px-4 py-3">
              <h2 className="text-sm font-semibold">设置</h2>
              <button
                onClick={() => setOpen(false)}
                className="grid h-7 w-7 place-items-center rounded-md text-[var(--text-muted)] hover:bg-[var(--surface-alt)] hover:text-[var(--text-primary)]"
              >
                <X size={15} />
              </button>
            </div>

            <div className="space-y-4 px-4 py-4 max-h-96 overflow-y-auto">
              {/* Auto-index toggle */}
              <label className="flex items-center justify-between gap-3">
                <span className="text-sm font-medium text-[var(--text-primary)]">打开时一键索引</span>
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

              {/* API section */}
              <div className="space-y-3 pt-2 border-t border-[var(--surface-border)]">
                <p className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wide">API 配置</p>
                <div>
                  <label className="block text-xs text-[var(--text-secondary)] mb-1">API Key</label>
                  <div className="relative">
                    <input
                      type={showApiKey ? "text" : "password"}
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder="sk-..."
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
                <div>
                  <label className="block text-xs text-[var(--text-secondary)] mb-1">Base URL</label>
                  <input
                    type="text"
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    placeholder="https://api.deepseek.com"
                    className="h-9 w-full rounded-md border border-[var(--surface-border)] bg-[var(--surface-bg)] px-3 text-sm outline-none transition-colors placeholder:text-[var(--text-muted)] focus:border-[var(--accent)]"
                  />
                </div>
              </div>

              {/* Sliders */}
              <div className="space-y-4 pt-2 border-t border-[var(--surface-border)]">
                <p className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wide">检索参数</p>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs text-[var(--text-secondary)]">Top K</label>
                    <span className="text-xs font-medium text-[var(--text-primary)]">{topK}</span>
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
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs text-[var(--text-secondary)]">Chunk Size</label>
                    <span className="text-xs font-medium text-[var(--text-primary)]">{chunkSize}</span>
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
                </div>
              </div>
            </div>

            <div className="border-t border-[var(--surface-border)] px-4 py-3">
              <div className="flex items-center justify-between">
                {message && (
                  <span className="text-xs text-[var(--success)]">{message}</span>
                )}
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="ml-auto inline-flex h-8 items-center rounded-md bg-[var(--accent)] px-4 text-xs font-medium text-white transition-colors hover:bg-[var(--accent-hover)] disabled:opacity-50"
                >
                  {saving ? "保存中..." : "保存"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
