'use client';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { DynamicMcpForm } from './dynamic-mcp-form';
import { useMcpCatalogEntry, useCreateMcpConfig } from '@/lib/api/queries/use-mcp';
import { MCPConfigCreate, MCPConfigUpdate } from '@/lib/api/types';

interface AddMcpDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  /** mcp_key from catalog. Null when no MCP is selected yet. */
  mcpKey: string | null;
}

export function AddMcpDialog({
  open,
  onOpenChange,
  projectId,
  mcpKey,
}: AddMcpDialogProps) {
  const { data: entry, isLoading, error } = useMcpCatalogEntry(
    mcpKey ?? '',
    open && !!mcpKey
  );
  const createConfig = useCreateMcpConfig(projectId);

  function handleSubmit(payload: MCPConfigCreate | MCPConfigUpdate) {
    if (!mcpKey) return;
    // mode=create guarantees MCPConfigCreate
    createConfig.mutate(payload as MCPConfigCreate, {
      onSuccess: () => onOpenChange(false),
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            Configure {entry?.name ?? 'MCP'}
            {entry && (
              <Badge variant="outline" className="text-xs font-mono">
                {entry.key}
              </Badge>
            )}
          </DialogTitle>
          <DialogDescription>
            {entry?.description ?? 'Configure secrets and settings for this MCP server.'}
          </DialogDescription>
        </DialogHeader>

        {isLoading && (
          <div className="flex items-center justify-center py-12 text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Loading catalog entry…
          </div>
        )}

        {error && (
          <div className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
            Failed to load catalog entry:{' '}
            {error instanceof Error ? error.message : 'Unknown error'}
          </div>
        )}

        {entry && (
          <ScrollArea className="max-h-[65vh] pr-4">
            <DynamicMcpForm
              entry={entry}
              mode="create"
              onSubmit={handleSubmit}
              onCancel={() => onOpenChange(false)}
              isSubmitting={createConfig.isPending}
            />
          </ScrollArea>
        )}
      </DialogContent>
    </Dialog>
  );
}
