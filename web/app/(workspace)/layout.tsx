"use client";

import { useState, useEffect } from "react";
import ProjectSidebar from "@/components/workspace/ProjectSidebar";
import { getFiles, ingestFiles } from "@/lib/api";

export default function WorkspaceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // 全局自动索引：勾选"打开时一键索引"后在应用启动时自动执行
  useEffect(() => {
    const stored = localStorage.getItem("co-thinker-auto-index");
    const autoIndex = stored !== null ? stored === "true" : true;
    if (!autoIndex) return;

    let cancelled = false;
    getFiles()
      .then((data) => {
        if (cancelled) return;
        const files = data.files || [];
        const unindexedPaths = files
          .filter((f: { is_dir?: boolean; is_indexed?: boolean }) => !f.is_dir && !f.is_indexed)
          .map((f: { path: string }) => f.path);
        if (unindexedPaths.length === 0) return;
        return ingestFiles(unindexedPaths).then(() => {
          if (!cancelled) {
            window.dispatchEvent(new CustomEvent("index-updated"));
          }
        });
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="flex h-full min-h-screen bg-[var(--surface-bg)]">
      <ProjectSidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />
      <main
        className={`min-w-0 flex-1 overflow-auto transition-all duration-200 ${
          sidebarCollapsed ? "ml-0" : ""
        }`}
      >
        {children}
      </main>
    </div>
  );
}
