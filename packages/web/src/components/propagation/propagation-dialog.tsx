'use client';

import { useState } from 'react';
import { 
  AlertCircle, 
  CheckCircle2, 
  GitBranch, 
  Loader2,
  Package,
  Share2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { usePreviewPropagation, usePropagatDecision } from '@/lib/api/queries';
import { PropagationScope, PropagationPreview, PropagationResult } from '@/lib/api/types';

interface PropagationDialogProps {
  projectSlug: string;
  decisionId: string;
  decisionType: string;
  question: string;
  resolution: string;
  trigger?: React.ReactNode;
  onSuccess?: (result: PropagationResult) => void;
}

export function PropagationDialog({
  projectSlug,
  decisionId,
  decisionType,
  question,
  resolution,
  trigger,
  onSuccess,
}: PropagationDialogProps) {
  const [open, setOpen] = useState(false);
  const [scope, setScope] = useState<PropagationScope>(PropagationScope.PROJECT);
  const [preview, setPreview] = useState<PropagationPreview | null>(null);
  const [result, setResult] = useState<PropagationResult | null>(null);

  const previewMutation = usePreviewPropagation(projectSlug);
  const propagateMutation = usePropagatDecision(projectSlug);

  const handlePreview = async () => {
    try {
      const data = await previewMutation.mutateAsync({
        decisionId,
        scope,
      });
      setPreview(data);
    } catch (error) {
      console.error('Preview failed:', error);
    }
  };

  const handlePropagate = async () => {
    try {
      const data = await propagateMutation.mutateAsync({
        decisionId,
        scope,
      });
      setResult(data);
      onSuccess?.(data);
    } catch (error) {
      console.error('Propagation failed:', error);
    }
  };

  const handleOpenChange = (newOpen: boolean) => {
    setOpen(newOpen);
    if (!newOpen) {
      // Reset state when closing
      setPreview(null);
      setResult(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        {trigger || (
          <Button variant="outline" size="sm" className="gap-2">
            <Share2 className="h-4 w-4" />
            Propagate
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <GitBranch className="h-5 w-5 text-primary" />
            Propagate Decision
          </DialogTitle>
          <DialogDescription>
            Apply this resolution to all packages with the same question.
          </DialogDescription>
        </DialogHeader>

        {/* Decision Info */}
        <div className="space-y-3 py-2">
          <div>
            <p className="text-sm font-medium text-muted-foreground">Decision Type</p>
            <p className="text-sm font-mono">{decisionType}</p>
          </div>
          <div>
            <p className="text-sm font-medium text-muted-foreground">Question</p>
            <p className="text-sm">{question}</p>
          </div>
          <div>
            <p className="text-sm font-medium text-muted-foreground">Resolution</p>
            <p className="text-sm">{resolution}</p>
          </div>
        </div>

        {/* Scope Selection */}
        <div className="space-y-2">
          <p className="text-sm font-medium">Propagation Scope</p>
          <Select value={scope} onValueChange={(v) => setScope(v as PropagationScope)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={PropagationScope.PROJECT}>
                All packages in project
              </SelectItem>
              <SelectItem value={PropagationScope.CLUSTER}>
                Same cluster only
              </SelectItem>
              <SelectItem value={PropagationScope.DOMAIN}>
                Same domain only
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Preview */}
        {preview && !result && (
          <div className="space-y-3 border rounded-lg p-3 bg-muted/50">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Preview</span>
              <div className="flex gap-3 text-sm">
                <span className="text-green-600">
                  {preview.would_affect_count} would be resolved
                </span>
                <span className="text-muted-foreground">
                  {preview.already_resolved_count} already resolved
                </span>
              </div>
            </div>
            
            {preview.affected_packages.length > 0 && (
              <ScrollArea className="h-32">
                <div className="space-y-1">
                  {preview.affected_packages.map((pkg) => (
                    <div
                      key={pkg.id}
                      className="flex items-center gap-2 text-sm py-1 px-2 rounded bg-background"
                    >
                      <Package className="h-3 w-3 text-muted-foreground" />
                      <span className="truncate">{pkg.name}</span>
                      {pkg.domain && (
                        <Badge variant="outline" className="text-xs">
                          {pkg.domain}
                        </Badge>
                      )}
                    </div>
                  ))}
                </div>
              </ScrollArea>
            )}
          </div>
        )}

        {/* Result */}
        {result && (
          <div className={cn(
            'space-y-2 border rounded-lg p-3',
            result.errors.length > 0 ? 'border-amber-500 bg-amber-50 dark:bg-amber-950' : 'border-green-500 bg-green-50 dark:bg-green-950'
          )}>
            <div className="flex items-center gap-2">
              {result.errors.length === 0 ? (
                <CheckCircle2 className="h-5 w-5 text-green-600" />
              ) : (
                <AlertCircle className="h-5 w-5 text-amber-600" />
              )}
              <span className="font-medium">
                Propagated to {result.packages_affected} package{result.packages_affected !== 1 ? 's' : ''}
              </span>
            </div>
            {result.errors.length > 0 && (
              <ul className="text-sm text-amber-700 dark:text-amber-300 space-y-1">
                {result.errors.map((err, i) => (
                  <li key={i}>• {err}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        <DialogFooter>
          {!result ? (
            <>
              {!preview ? (
                <Button
                  onClick={handlePreview}
                  disabled={previewMutation.isPending}
                  variant="outline"
                >
                  {previewMutation.isPending && (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  )}
                  Preview
                </Button>
              ) : (
                <Button
                  onClick={handlePropagate}
                  disabled={propagateMutation.isPending || preview.would_affect_count === 0}
                >
                  {propagateMutation.isPending && (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  )}
                  Apply to {preview.would_affect_count} Package{preview.would_affect_count !== 1 ? 's' : ''}
                </Button>
              )}
            </>
          ) : (
            <Button onClick={() => handleOpenChange(false)}>
              Done
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
