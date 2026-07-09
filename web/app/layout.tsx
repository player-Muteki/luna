import type { Metadata } from "next";
import "katex/dist/katex.min.css";
import "highlight.js/styles/github.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Co-Thinker",
  description: "基于 RAG 的工作目录知识库系统",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body className="h-full">{children}</body>
    </html>
  );
}
