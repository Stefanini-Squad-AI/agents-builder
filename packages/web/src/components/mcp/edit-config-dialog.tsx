'use client';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Loader2 } from 'lucide-react';
import { DynamicMcpForm } from './dynamic-mcp-form';
import {
  useMcpConfig,
  useMcpCatalogEntry,
  useUpdateMcpConfig,
} from '@/lib/api/queries/use-mcp';
import { MCPConfigCreate, MCPConfigUpdate } from '@/lib/api/types';

interface EditConfigDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  configId: string | null;
}

export function EditConfigDialog({
  open,
  onOpenChange,
  projectId,
  configId,
}: EditConfigDialogProps) {
  const {
    data: config,
    isLoading: configLoading,
    error: configError,
  } = useMcpConfig(projectId, configId ?? '', open && !!configId);

  const {
    data: entry,
    isLoading: entryLoading,
    error: entryError,
  } = useMcpCatalogEntry(config?.mcp_key ?? '', !!config?.mcp_key);

  const updateConfig = useUpdateMcpConfig(projectId);

  const isLoading = configLoading || entryLoading;
  const error = configError ?? entryError;

  function handleSubmit(payload: MCPConfigCreate | MCPConfigUpdate) {
    if (!configId) return;
    updateConfig.mutate(
      { configId, payload: payload as MCPConfigUpdate },
      { onSuccess: () => onOpenChange(false) }
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            Edit {config?.mcp_name ?? 'MCP'} configuration
            {entry && (
              <Badge variant="outline" className="text-xs font-mono">
                {entry.key}
              </Badge>
            )}
          </DialogTitle>
          <DialogDescription>
            Update env vars and config fields. Leave secret fields blank to keep
            the existing value.
          </DialogDescription>
        </DialogHeader>

        {isLoading && (
          <div className="flex items-center justify-center py-12 text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Loading…
          </div>
        )}

        {error && (
          <div className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
            Failed to load:{' '}
            {error instanceof Error ? error.message : 'Unknown error'}
          </div>
        )}

        {entry && config && (
          <ScrollArea className="max-h-[65vh] pr-4">
            <DynamicMcpForm
              entry={entry}
              mode="edit"
              existing={config}
              onSubmit={handleSubmit}
              onCancel={() => onOpenChange(false)}
              isSubmitting={updateConfig.isPending}
            />
          </ScrollArea>
        )}
      </DialogContent>
    </Dialog>
  );
}
