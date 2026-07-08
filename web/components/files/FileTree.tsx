"use client";

import { useState } from "react";
import { File, FileText, Folder, FolderOpen, CheckSquare, Square, ChevronRight, ChevronDown } from "lucide-react";

interface FileItem {
  path: string;
  name: string;
  ext: string;
  size: number;
  mtime: number;
  is_dir: boolean;
  is_indexed: boolean;
  document_id: string;
}

interface FileTreeProps {
  files: FileItem[];
  selected: Set<string>;
  onToggle: (path: string) => void;
}

const extIcon: Record<string, JSX.Element> = {};
const FileIcon = <File size={16} className="text-[var(--text-secondary)]" />;
const FileTextIcon = <FileText size={16} className="text-blue-400" />;

function getFileIcon(ext: string): JSX.Element {
  if ([".md", ".txt", ".py", ".js", ".ts", ".rs", ".go", ".java"].includes(ext)) {
    return FileTextIcon;
  }
  return FileIcon;
}

export default function FileTree({ files, selected, onToggle }: FileTreeProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set(["", "root"]));

  // Build tree structure
  interface TreeNode {
    name: string;
    path: string;
    is_dir: boolean;
    children: TreeNode[];
    file?: FileItem;
  }

  const root: TreeNode = { name: "", path: "", is_dir: true, children: [] };

  for (const f of files) {
    const parts = f.path.split("/");
    let current = root;
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isLast = i === parts.length - 1;
      const childPath = parts.slice(0, i + 1).join("/");

      let child = current.children.find((c) => c.name === part);
      if (!child) {
        child = {
          name: part,
          path: childPath,
          is_dir: !isLast || f.is_dir,
          children: [],
          file: isLast ? f : undefined,
        };
        current.children.push(child);
      } else if (isLast) {
        child.file = f;
      }
      current = child;
    }
  }

  const toggleExpand = (path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const renderNode = (node: TreeNode, depth: number) => {
    const isExpanded = expanded.has(node.path);
    const isSelected = node.file && selected.has(node.path);
    const hasChildren = node.children.length > 0;

    return (
      <div key={node.path}>
        <div
          className="flex items-center gap-1 px-2 py-1 rounded hover:bg-[var(--surface-alt)] cursor-pointer text-sm"
          style={{ paddingLeft: `${depth * 16 + 8}px` }}
        >
          {node.is_dir && hasChildren ? (
            <span
              onClick={() => toggleExpand(node.path)}
              className="p-0.5 hover:bg-[var(--surface-alt)] rounded"
            >
              {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </span>
          ) : node.is_dir ? (
            <span className="w-[22px]" />
          ) : (
            <span
              onClick={() => node.file && onToggle(node.path)}
              className="p-0.5 cursor-pointer"
            >
              {isSelected ? (
                <CheckSquare size={14} className="text-[var(--accent)]" />
              ) : (
                <Square size={14} className="text-[var(--text-secondary)]" />
              )}
            </span>
          )}

          {node.is_dir ? (
            isExpanded ? (
              <FolderOpen size={16} className="text-yellow-500" />
            ) : (
              <Folder size={16} className="text-yellow-500" />
            )
          ) : node.file ? (
            getFileIcon(node.file.ext)
          ) : null}

          <span
            className="flex-1 truncate"
            onClick={() => {
              if (node.is_dir && hasChildren) toggleExpand(node.path);
            }}
          >
            {node.name}
          </span>

          {node.file?.is_indexed && (
            <span className="text-xs text-green-500 bg-green-500/10 px-1.5 py-0.5 rounded">
              已索引
            </span>
          )}
        </div>

        {node.is_dir && isExpanded && hasChildren && (
          <div>
            {node.children.map((child) => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return <div>{root.children.map((child) => renderNode(child, 0))}</div>;
}
