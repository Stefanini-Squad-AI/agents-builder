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
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useCreateGap } from '@/lib/api/queries/use-gaps';

interface AddGapDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectSlug: string;
}

export function AddGapDialog({
  open,
  onOpenChange,
  projectSlug,
}: AddGapDialogProps) {
  const [title, setTitle] = useState('');
  const createGap = useCreateGap(projectSlug);

  function reset() {
    setTitle('');
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = title.trim();
    if (!trimmed) return;
    createGap.mutate(
      { title: trimmed },
      {
        onSuccess: () => {
          reset();
          onOpenChange(false);
        },
      }
    );
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) reset();
        onOpenChange(next);
      }}
    >
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Add gap</DialogTitle>
            <DialogDescription>
              Manually flag a coverage gap that ProposeSkillSet didn&apos;t
              detect.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-2 py-4">
            <Label htmlFor="gap-title">Title</Label>
            <Input
              id="gap-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. No skill covers secrets rotation"
              maxLength={500}
              autoFocus
              required
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={createGap.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!title.trim() || createGap.isPending}
            >
              {createGap.isPending ? 'Creating…' : 'Create gap'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
