'use client';

import { GapView, MCPConfigSummary } from '@/lib/api/types';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { GapStatusBadge } from './gap-status-badge';
import { McpNotConfiguredWarning } from './mcp-not-configured-warning';
import {
  MoreHorizontal,
  Sparkles,
  Plug,
  CircleSlash,
  RotateCcw,
  Trash2,
} from 'lucide-react';
import { useReopenGap, useDeleteGap } from '@/lib/api/queries/use-gaps';
import { useState } from 'react';

interface GapRowProps {
  gap: GapView;
  projectSlug: string;
  mcpConfigs: MCPConfigSummary[] | undefined;
  onAddressBySkill: (gap: GapView) => void;
  onCoverByMcp: (gap: GapView) => void;
  onMarkOutOfScope: (gap: GapView) => void;
}

export function GapRow({
  gap,
  projectSlug,
  mcpConfigs,
  onAddressBySkill,
  onCoverByMcp,
  onMarkOutOfScope,
}: GapRowProps) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const reopen = useReopenGap(projectSlug);
  const deleteGap = useDeleteGap(projectSlug);

  const isOpen = gap.status === 'open';
  const isResolved = gap.status !== 'open';
  const canDelete = gap.source === 'manual';

  // Detect MCP-not-configured case
  const mcpNotConfigured =
    gap.status === 'covered_by_mcp' &&
    gap.covered_by_mcp_key !== null &&
    mcpConfigs !== undefined &&
    !mcpConfigs.some((c) => c.mcp_key === gap.covered_by_mcp_key);

  return (
    <div className="rounded-lg border bg-card p-4 transition-colors hover:bg-accent/30">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <GapStatusBadge status={gap.status} />
            <span className="text-xs text-muted-foreground">
              {gap.source === 'propose_skill_set' ? 'detected' : 'manual'}
            </span>
          </div>

          <h4 className="text-sm font-medium leading-snug">{gap.title}</h4>

          {gap.decision_rationale && (
            <p className="text-xs text-muted-foreground">
              <span className="font-medium">Rationale:</span>{' '}
              {gap.decision_rationale}
            </p>
          )}

          {gap.status === 'covered_by_mcp' && gap.covered_by_mcp_key && (
            <p className="text-xs text-muted-foreground">
              <span className="font-medium">MCP:</span>{' '}
              <code className="font-mono text-[11px]">
                {gap.covered_by_mcp_key}
              </code>
            </p>
          )}

          {mcpNotConfigured && gap.covered_by_mcp_key && (
            <McpNotConfiguredWarning
              projectSlug={projectSlug}
              mcpKey={gap.covered_by_mcp_key}
            />
          )}
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0">
              <MoreHorizontal className="h-4 w-4" />
              <span className="sr-only">Gap actions</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            {isOpen && (
              <>
                <DropdownMenuItem onClick={() => onAddressBySkill(gap)}>
                  <Sparkles className="mr-2 h-4 w-4" />
                  Address by skill
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => onCoverByMcp(gap)}>
                  <Plug className="mr-2 h-4 w-4" />
                  Cover by MCP
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => onMarkOutOfScope(gap)}>
                  <CircleSlash className="mr-2 h-4 w-4" />
                  Mark out of scope
                </DropdownMenuItem>
              </>
            )}
            {isResolved && (
              <DropdownMenuItem
                onClick={() => reopen.mutate(gap.id)}
                disabled={reopen.isPending}
              >
                <RotateCcw className="mr-2 h-4 w-4" />
                Reopen
              </DropdownMenuItem>
            )}
            {canDelete && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive"
                  onClick={() => setConfirmDelete(true)}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete gap
                </DropdownMenuItem>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete gap?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete <strong>{gap.title}</strong>. This
              action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteGap.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                deleteGap.mutate(gap.id, {
                  onSuccess: () => setConfirmDelete(false),
                });
              }}
              disabled={deleteGap.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteGap.isPending ? 'Deleting…' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
