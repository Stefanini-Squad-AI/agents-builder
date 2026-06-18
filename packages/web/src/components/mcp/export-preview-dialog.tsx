'use client';

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Loader2, Download, ShieldAlert } from 'lucide-react';
import { useMcpExportPreview, downloadMcpJson } from '@/lib/api/queries/use-mcp';

interface ExportPreviewDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
}

export function ExportPreviewDialog({
  open,
  onOpenChange,
  projectId,
}: ExportPreviewDialogProps) {
  const [downloading, setDownloading] = useState(false);
  const { data: preview, isLoading, error } = useMcpExportPreview(
    projectId,
    open
  );

  async function handleDownload() {
    setDownloading(true);
    try {
      await downloadMcpJson(projectId);
      onOpenChange(false);
    } catch {
      // toast is shown inside downloadMcpJson
    } finally {
      setDownloading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Export mcp.json</DialogTitle>
          <DialogDescription>
            Review what will be exported before downloading.
          </DialogDescription>
        </DialogHeader>

        {isLoading && (
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Loading preview…
          </div>
        )}

        {error && (
          <div className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
            Failed to load preview:{' '}
            {error instanceof Error ? error.message : 'Unknown error'}
          </div>
        )}

        {preview && (
          <div className="space-y-4">
            <div className="grid gap-2 rounded-md border bg-card p-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Servers</span>
                <span className="font-semibold">{preview.server_count}</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {preview.servers.map((key) => (
                  <Badge key={key} variant="secondary" className="font-mono text-xs">
                    {key}
                  </Badge>
                ))}
                {preview.servers.length === 0 && (
                  <span className="text-xs text-muted-foreground">
                    No enabled servers — nothing will be exported.
                  </span>
                )}
              </div>
            </div>

            {preview.has_secrets && (
              <div className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-900 dark:text-amber-200">
                <ShieldAlert className="mt-0.5 h-4 w-4 text-amber-600 dark:text-amber-400" />
                <span>
                  <strong>{preview.warning}</strong> The downloaded file will
                  contain decrypted secret values in <code>env</code> entries.
                  Do not commit it to source control.
                </span>
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={downloading}
          >
            Cancel
          </Button>
          <Button
            onClick={handleDownload}
            disabled={
              downloading ||
              isLoading ||
              !preview ||
              preview.server_count === 0
            }
          >
            <Download className="mr-2 h-4 w-4" />
            {downloading ? 'Downloading…' : 'Download mcp.json'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
