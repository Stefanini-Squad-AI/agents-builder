'use client';

import { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { DagNodeView, CardType, CardStatus } from '@/lib/api/types';
import { cn } from '@/lib/utils';
import { FileText, Lightbulb, Flag, Wrench, Presentation, Circle, Bug } from 'lucide-react';

// Card type icons
const typeIcons: Record<CardType, React.ElementType> = {
  [CardType.STORY]: FileText,
  [CardType.TASK]: Wrench,
  [CardType.BUG]: Bug,
  [CardType.SPIKE]: Lightbulb,
  [CardType.DEMO]: Presentation,
};

// Status colors
const statusColors: Record<CardStatus, string> = {
  [CardStatus.DRAFT]: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
  [CardStatus.READY]: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  [CardStatus.IN_PROGRESS]: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  [CardStatus.DONE]: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
};

// Status labels
const statusLabels: Record<CardStatus, string> = {
  [CardStatus.DRAFT]: 'Draft',
  [CardStatus.READY]: 'Ready',
  [CardStatus.IN_PROGRESS]: 'In Progress',
  [CardStatus.DONE]: 'Done',
};

function CardNodeComponent({ data, selected }: NodeProps<DagNodeView>) {
  const TypeIcon = typeIcons[data.type] || FileText;

  return (
    <>
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-primary !w-3 !h-3"
      />
      <div
        className={cn(
          'px-4 py-3 rounded-lg border-2 bg-card shadow-md cursor-pointer transition-all min-w-[200px]',
          selected
            ? 'border-primary ring-2 ring-primary/20'
            : 'border-border hover:border-primary/50'
        )}
      >
        {/* Header */}
        <div className="flex items-center gap-2 mb-2">
          <TypeIcon className="h-4 w-4 text-muted-foreground shrink-0" />
          <span className="font-mono text-xs text-muted-foreground">{data.code}</span>
        </div>

        {/* Title */}
        <h3 className="text-sm font-medium leading-tight line-clamp-2 mb-2">
          {data.title}
        </h3>

        {/* Footer */}
        <div className="flex items-center justify-between gap-2 text-xs">
          <span
            className={cn(
              'px-2 py-0.5 rounded-full font-medium',
              statusColors[data.status]
            )}
          >
            {statusLabels[data.status]}
          </span>
          <div className="flex items-center gap-2 text-muted-foreground">
            {data.story_points && (
              <span className="flex items-center gap-1">
                <Circle className="h-3 w-3 fill-current" />
                {data.story_points}
              </span>
            )}
            <span>{data.phase_code}</span>
          </div>
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Right}
        className="!bg-primary !w-3 !h-3"
      />
    </>
  );
}

export const CardNode = memo(CardNodeComponent);
