'use client';

import { useState, useCallback } from 'react';
import { ExportTreeNode } from '@/lib/api/types';
import { cn } from '@/lib/utils';
import { ChevronRight, ChevronDown, Folder, FolderOpen, FileText } from 'lucide-react';

function formatBytes(bytes: number | undefined): string {
  if (!bytes || bytes === 0) return '';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

interface TreeNodeProps {
  node: ExportTreeNode;
  depth: number;
  defaultExpanded?: boolean;
}

function TreeNode({ node, depth, defaultExpanded = false }: TreeNodeProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded || depth < 2);
  const isDirectory = node.type === 'directory';
  const hasChildren = isDirectory && node.children && node.children.length > 0;

  const handleToggle = useCallback(() => {
    if (hasChildren) {
      setIsExpanded((prev) => !prev);
    }
  }, [hasChildren]);

  return (
    <div>
      <div
        className={cn(
          'flex items-center gap-1 py-1 px-2 rounded hover:bg-accent/50 cursor-pointer transition-colors',
          'text-sm'
        )}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={handleToggle}
      >
        {/* Expand/collapse icon */}
        {hasChildren ? (
          isExpanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
          )
        ) : (
          <span className="w-4 shrink-0" />
        )}

        {/* Icon */}
        {isDirectory ? (
          isExpanded ? (
            <FolderOpen className="h-4 w-4 text-yellow-500 shrink-0" />
          ) : (
            <Folder className="h-4 w-4 text-yellow-500 shrink-0" />
          )
        ) : (
          <FileText className="h-4 w-4 text-blue-500 shrink-0" />
        )}

        {/* Name */}
        <span className={cn('flex-1 truncate', isDirectory && 'font-medium')}>
          {node.name}
        </span>

        {/* Size (for files) */}
        {!isDirectory && node.size && (
          <span className="text-xs text-muted-foreground shrink-0">
            {formatBytes(node.size)}
          </span>
        )}

        {/* Child count (for directories) */}
        {isDirectory && hasChildren && (
          <span className="text-xs text-muted-foreground shrink-0">
            {node.children!.length} items
          </span>
        )}
      </div>

      {/* Children */}
      {hasChildren && isExpanded && (
        <div>
          {node.children!.map((child, index) => (
            <TreeNode
              key={`${child.name}-${index}`}
              node={child}
              depth={depth + 1}
              defaultExpanded={depth < 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface ExportTreeViewProps {
  tree: ExportTreeNode[];
}

export function ExportTreeView({ tree }: ExportTreeViewProps) {
  if (!tree || tree.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No files to export
      </div>
    );
  }

  return (
    <div className="border rounded-lg overflow-hidden max-h-[400px] overflow-y-auto">
      <div className="py-2">
        {tree.map((node, index) => (
          <TreeNode key={`${node.name}-${index}`} node={node} depth={0} defaultExpanded />
        ))}
      </div>
    </div>
  );
}
