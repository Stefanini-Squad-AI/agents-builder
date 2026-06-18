'use client';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { FileText, AlertTriangle } from 'lucide-react';
import { ArtifactSummary } from '@/lib/api/types';

interface ArtifactPreviewProps {
  artifact: ArtifactSummary | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Modal dialog for previewing extracted artifact content.
 */
export function ArtifactPreview({
  artifact,
  open,
  onOpenChange,
}: ArtifactPreviewProps) {
  if (!artifact) return null;

  const hasContent = !!artifact.content_md_excerpt;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-lg bg-muted shrink-0">
              <FileText className="h-5 w-5 text-muted-foreground" />
            </div>
            <div className="min-w-0 flex-1">
              <DialogTitle className="truncate">{artifact.filename}</DialogTitle>
              <DialogDescription className="flex items-center gap-2 mt-1">
                <Badge variant="outline" className="capitalize">
                  {artifact.kind}
                </Badge>
                {artifact.content_md_truncated && (
                  <Badge variant="secondary" className="gap-1">
                    <AlertTriangle className="h-3 w-3" />
                    Content truncated
                  </Badge>
                )}
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="flex-1 min-h-0 mt-4">
          {hasContent ? (
            <ScrollArea className="h-[50vh] border rounded-lg">
              <pre className="p-4 text-sm font-mono whitespace-pre-wrap break-words">
                {artifact.content_md_excerpt}
              </pre>
            </ScrollArea>
          ) : (
            <div className="flex flex-col items-center justify-center h-[200px] text-muted-foreground">
              <FileText className="h-12 w-12 mb-4 opacity-40" />
              <p>No content preview available</p>
            </div>
          )}
        </div>

        {artifact.content_md_truncated && (
          <p className="text-sm text-muted-foreground mt-4">
            This preview shows the first 2000 characters. The full content is stored
            and will be used for LLM context.
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default ArtifactPreview;
