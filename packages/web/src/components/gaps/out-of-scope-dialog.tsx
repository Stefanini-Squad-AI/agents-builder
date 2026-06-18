'use client';

import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { GapView } from '@/lib/api/types';
import { useMarkGapOutOfScope } from '@/lib/api/queries/use-gaps';

interface OutOfScopeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectSlug: string;
  gap: GapView | null;
}

export function OutOfScopeDialog({
  open,
  onOpenChange,
  projectSlug,
  gap,
}: OutOfScopeDialogProps) {
  const [rationale, setRationale] = useState('');
  const mutation = useMarkGapOutOfScope(projectSlug);

  useEffect(() => {
    if (!open) setRationale('');
  }, [open]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!gap) return;
    mutation.mutate(
      {
        gapId: gap.id,
        payload: { rationale: rationale.trim() || undefined },
      },
      { onSuccess: () => onOpenChange(false) }
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Mark as out of scope</DialogTitle>
            <DialogDescription>
              {gap ? (
                <>
                  Acknowledge that <strong>{gap.title}</strong> is intentionally
                  not covered by this project.
                </>
              ) : (
                'Acknowledge that this gap is intentionally not covered.'
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-2 py-4">
            <Label htmlFor="oos-rationale">Rationale (optional)</Label>
            <Textarea
              id="oos-rationale"
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              placeholder="Why is this out of scope?"
              rows={3}
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={mutation.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? 'Saving…' : 'Mark out of scope'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
