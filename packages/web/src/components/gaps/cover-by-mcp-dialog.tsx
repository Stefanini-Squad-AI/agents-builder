'use client';

import { useState, useEffect, useMemo } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { GapView } from '@/lib/api/types';
import { useMcpCatalog, useMcpConfigs } from '@/lib/api/queries/use-mcp';
import { useCoverGapByMcp } from '@/lib/api/queries/use-gaps';

interface CoverByMcpDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectSlug: string;
  projectId: string | undefined;
  gap: GapView | null;
}

export function CoverByMcpDialog({
  open,
  onOpenChange,
  projectSlug,
  projectId,
  gap,
}: CoverByMcpDialogProps) {
  const [mcpKey, setMcpKey] = useState<string>('');
  const [rationale, setRationale] = useState('');

  const { data: configs } = useMcpConfigs(projectId ?? '', false, !!projectId && open);
  const { data: catalog } = useMcpCatalog(undefined, open);
  const coverMutation = useCoverGapByMcp(projectSlug);

  useEffect(() => {
    if (!open) {
      setMcpKey('');
      setRationale('');
    }
  }, [open]);

  // Configured keys deduped
  const configuredKeys = useMemo(
    () => new Set((configs ?? []).map((c) => c.mcp_key)),
    [configs]
  );

  // Catalog entries that are NOT yet configured for this project
  const catalogOnly = useMemo(
    () => (catalog ?? []).filter((c) => !configuredKeys.has(c.key)),
    [catalog, configuredKeys]
  );

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!gap || !mcpKey) return;
    coverMutation.mutate(
      {
        gapId: gap.id,
        payload: {
          mcp_key: mcpKey,
          rationale: rationale.trim() || undefined,
        },
      },
      { onSuccess: () => onOpenChange(false) }
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Cover by MCP</DialogTitle>
            <DialogDescription>
              {gap ? (
                <>Choose an MCP server that covers <strong>{gap.title}</strong>.</>
              ) : (
                'Choose an MCP server that covers this gap.'
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="mcp-select">MCP server</Label>
              <Select value={mcpKey} onValueChange={setMcpKey}>
                <SelectTrigger id="mcp-select">
                  <SelectValue placeholder="Select an MCP" />
                </SelectTrigger>
                <SelectContent>
                  {(configs ?? []).length > 0 && (
                    <SelectGroup>
                      <SelectLabel>✅ Configured in this project</SelectLabel>
                      {(configs ?? []).map((c) => (
                        <SelectItem key={c.mcp_key} value={c.mcp_key}>
                          <span className="flex items-center gap-2">
                            {c.mcp_name}
                            {!c.enabled && (
                              <Badge variant="outline" className="text-xs">
                                disabled
                              </Badge>
                            )}
                          </span>
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  )}
                  {catalogOnly.length > 0 && (
                    <SelectGroup>
                      <SelectLabel>📚 From catalog (not configured)</SelectLabel>
                      {catalogOnly.map((entry) => (
                        <SelectItem key={entry.key} value={entry.key}>
                          {entry.name}
                          <span className="ml-2 text-xs text-muted-foreground">
                            {entry.vendor}
                          </span>
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  )}
                  {(configs?.length ?? 0) === 0 && catalogOnly.length === 0 && (
                    <SelectItem value="__none" disabled>
                      No MCPs available
                    </SelectItem>
                  )}
                </SelectContent>
              </Select>
              {mcpKey && !configuredKeys.has(mcpKey) && (
                <p className="text-xs text-muted-foreground">
                  This MCP is not configured yet. You can configure it later
                  from the MCP Integrations page.
                </p>
              )}
            </div>

            <div className="grid gap-2">
              <Label htmlFor="cover-rationale">Rationale (optional)</Label>
              <Textarea
                id="cover-rationale"
                value={rationale}
                onChange={(e) => setRationale(e.target.value)}
                placeholder="Why does this MCP cover the gap?"
                rows={3}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={coverMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!mcpKey || coverMutation.isPending}
            >
              {coverMutation.isPending ? 'Saving…' : 'Cover gap'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
