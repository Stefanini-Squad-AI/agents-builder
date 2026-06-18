'use client';

import { useState } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Download, FolderTree, Eye, AlertCircle, ShieldAlert } from 'lucide-react';
import { useMcpExportPreview } from '@/lib/api/queries/use-mcp';
import { ExportPreviewDialog } from './export-preview-dialog';

interface ExportPanelProps {
  projectId: string;
}

export function ExportPanel({ projectId }: ExportPanelProps) {
  const [previewOpen, setPreviewOpen] = useState(false);
  const { data: preview, isLoading, error } = useMcpExportPreview(projectId);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start gap-3">
          <FolderTree className="mt-1 h-5 w-5 text-primary" />
          <div className="flex-1">
            <CardTitle>Export to .cursor/mcp.json</CardTitle>
            <CardDescription>
              Generate the Cursor IDE configuration file that includes all
              enabled MCP servers for this project.
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            <AlertCircle className="mt-0.5 h-4 w-4" />
            <span>
              {error instanceof Error ? error.message : 'Failed to load preview'}
            </span>
          </div>
        )}

        {isLoading ? (
          <Skeleton className="h-20 w-full rounded-md" />
        ) : preview ? (
          <div className="rounded-md border bg-muted/30 p-4">
            <div className="mb-2 flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Enabled servers</span>
              <span className="font-semibold">{preview.server_count}</span>
            </div>
            {preview.servers.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {preview.servers.map((key) => (
                  <Badge key={key} variant="secondary" className="font-mono text-xs">
                    {key}
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                No MCPs are currently enabled. Enable at least one MCP in the
                Configured tab to make this export non-empty.
              </p>
            )}
          </div>
        ) : null}

        {preview?.has_secrets && (
          <div className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-900 dark:text-amber-200">
            <ShieldAlert className="mt-0.5 h-4 w-4 text-amber-600 dark:text-amber-400" />
            <span>
              The exported file contains decrypted secrets. Treat
              <code className="mx-1 rounded bg-background/50 px-1">mcp.json</code>
              as sensitive and add it to your <code>.gitignore</code>.
            </span>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <Button onClick={() => setPreviewOpen(true)} disabled={isLoading}>
            <Eye className="mr-2 h-4 w-4" />
            Preview
          </Button>
          <Button
            variant="outline"
            disabled={
              isLoading || !preview || preview.server_count === 0
            }
            onClick={() => setPreviewOpen(true)}
          >
            <Download className="mr-2 h-4 w-4" />
            Download
          </Button>
        </div>
      </CardContent>

      <ExportPreviewDialog
        open={previewOpen}
        onOpenChange={setPreviewOpen}
        projectId={projectId}
      />
    </Card>
  );
}
