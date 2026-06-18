'use client';

import { Badge } from '@/components/ui/badge';
import { GapStatus } from '@/lib/api/types';
import { cn } from '@/lib/utils';

const STATUS_LABELS: Record<GapStatus, string> = {
  open: 'Open',
  addressed_by_skill: 'Addressed by skill',
  covered_by_mcp: 'Covered by MCP',
  out_of_scope: 'Out of scope',
};

const STATUS_STYLES: Record<GapStatus, string> = {
  open: 'border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400',
  addressed_by_skill:
    'border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
  covered_by_mcp:
    'border-sky-500/40 bg-sky-500/10 text-sky-700 dark:text-sky-400',
  out_of_scope:
    'border-muted-foreground/40 bg-muted text-muted-foreground',
};

interface GapStatusBadgeProps {
  status: GapStatus;
  className?: string;
}

export function GapStatusBadge({ status, className }: GapStatusBadgeProps) {
  return (
    <Badge
      variant="outline"
      className={cn(STATUS_STYLES[status], 'font-medium', className)}
    >
      {STATUS_LABELS[status]}
    </Badge>
  );
}
