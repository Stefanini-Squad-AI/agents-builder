'use client';

import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { AlertCircle, Plug } from 'lucide-react';
import { ConfigRow } from './config-row';
import { useMcpConfigs } from '@/lib/api/queries/use-mcp';

interface ConfiguredListProps {
  projectId: string;
  onEdit: (configId: string) => void;
}

export function ConfiguredList({ projectId, onEdit }: ConfiguredListProps) {
  const { data: configs, isLoading, error } = useMcpConfigs(projectId);

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Failed to load configurations</AlertTitle>
        <AlertDescription>
          {error instanceof Error ? error.message : 'Unknown error'}
        </AlertDescription>
      </Alert>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[...Array(3)].map((_, i) => (
          <Skeleton key={i} className="h-20 w-full rounded-lg" />
        ))}
      </div>
    );
  }

  if (!configs || configs.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-10 text-center">
        <Plug className="mx-auto h-8 w-8 text-muted-foreground/40" />
        <p className="mt-3 text-sm font-medium">No MCPs configured yet</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Browse the Catalog tab to add your first MCP server.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {configs.map((config) => (
        <ConfigRow
          key={config.id}
          projectId={projectId}
          config={config}
          onEdit={onEdit}
        />
      ))}
    </div>
  );
}
