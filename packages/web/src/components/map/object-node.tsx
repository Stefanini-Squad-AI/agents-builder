'use client';

import { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { cn } from '@/lib/utils';
import { Database, FileText, Globe, MessageSquare, Radio } from 'lucide-react';
import { MapObjectType } from '@/lib/api/types';

// Object node data type
export interface ObjectNodeData {
  label: string;
  objectType: MapObjectType;
  schemaName?: string;
  connectionRef?: string;
  readByCount: number;
  writtenByCount: number;
}

// Type icons
const typeIcons: Record<MapObjectType, React.ElementType> = {
  [MapObjectType.TABLE]: Database,
  [MapObjectType.FILE]: FileText,
  [MapObjectType.API]: Globe,
  [MapObjectType.QUEUE]: MessageSquare,
  [MapObjectType.TOPIC]: Radio,
};

// Type colors
const typeColors: Record<MapObjectType, string> = {
  [MapObjectType.TABLE]: 'border-blue-500 bg-blue-50 dark:bg-blue-950',
  [MapObjectType.FILE]: 'border-amber-500 bg-amber-50 dark:bg-amber-950',
  [MapObjectType.API]: 'border-purple-500 bg-purple-50 dark:bg-purple-950',
  [MapObjectType.QUEUE]: 'border-cyan-500 bg-cyan-50 dark:bg-cyan-950',
  [MapObjectType.TOPIC]: 'border-pink-500 bg-pink-50 dark:bg-pink-950',
};

function ObjectNodeComponent({ data, selected }: NodeProps<ObjectNodeData>) {
  const TypeIcon = typeIcons[data.objectType] || Database;
  const colorClass = typeColors[data.objectType] || typeColors[MapObjectType.TABLE];

  return (
    <>
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-muted-foreground !w-2 !h-2"
      />
      <div
        className={cn(
          'px-3 py-2 rounded-md border shadow-sm cursor-pointer transition-all min-w-[150px]',
          colorClass,
          selected
            ? 'ring-2 ring-primary/30'
            : 'hover:shadow-md'
        )}
      >
        {/* Header with icon */}
        <div className="flex items-center gap-2 mb-1">
          <TypeIcon className="h-3 w-3 text-muted-foreground shrink-0" />
          <span className="text-xs font-mono text-muted-foreground uppercase">
            {data.objectType}
          </span>
        </div>

        {/* Object name */}
        <h4 className="text-xs font-medium leading-tight line-clamp-1 mb-1">
          {data.schemaName && (
            <span className="text-muted-foreground">{data.schemaName}.</span>
          )}
          {data.label}
        </h4>

        {/* Stats */}
        <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
          {data.readByCount > 0 && (
            <span title={`Read by ${data.readByCount} package(s)`}>
              ← {data.readByCount}
            </span>
          )}
          {data.writtenByCount > 0 && (
            <span title={`Written by ${data.writtenByCount} package(s)`}>
              → {data.writtenByCount}
            </span>
          )}
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Right}
        className="!bg-muted-foreground !w-2 !h-2"
      />
    </>
  );
}

export const ObjectNode = memo(ObjectNodeComponent);
