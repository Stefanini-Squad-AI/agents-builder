'use client';

import { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { cn } from '@/lib/utils';
import { Package, AlertCircle, CheckCircle2, Clock, Loader2 } from 'lucide-react';

// Package status enum
export type PackageStatus = 'pending' | 'analyzing' | 'analyzed' | 'failed';

// Package node data type
export interface PackageNodeData {
  label: string;
  status: PackageStatus;
  wave?: number;
  blockers?: number;
  autoResolved?: number;
}

// Status colors
const statusColors: Record<PackageStatus, string> = {
  pending: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
  analyzing: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  analyzed: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  failed: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
};

// Status icons
const StatusIcon = ({ status }: { status: PackageStatus }) => {
  switch (status) {
    case 'pending':
      return <Clock className="h-4 w-4 text-gray-500" />;
    case 'analyzing':
      return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
    case 'analyzed':
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    case 'failed':
      return <AlertCircle className="h-4 w-4 text-red-500" />;
  }
};

function PackageNodeComponent({ data, selected }: NodeProps<PackageNodeData>) {
  const blockerCount = data.blockers || 0;
  const autoResolved = data.autoResolved || 0;
  const pendingBlockers = blockerCount - autoResolved;

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
          <Package className="h-4 w-4 text-muted-foreground shrink-0" />
          <StatusIcon status={data.status} />
          {data.wave !== undefined && (
            <span className="ml-auto text-xs font-mono bg-primary/10 text-primary px-2 py-0.5 rounded">
              Wave {data.wave}
            </span>
          )}
        </div>

        {/* Title */}
        <h3 className="text-sm font-medium leading-tight line-clamp-2 mb-2">
          {data.label}
        </h3>

        {/* Footer */}
        <div className="flex items-center justify-between gap-2 text-xs">
          <span
            className={cn(
              'px-2 py-0.5 rounded-full font-medium capitalize',
              statusColors[data.status]
            )}
          >
            {data.status}
          </span>
          {pendingBlockers > 0 && (
            <span className="flex items-center gap-1 text-amber-600 dark:text-amber-400">
              <AlertCircle className="h-3 w-3" />
              {pendingBlockers} blocker{pendingBlockers > 1 ? 's' : ''}
            </span>
          )}
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

export const PackageNode = memo(PackageNodeComponent);
