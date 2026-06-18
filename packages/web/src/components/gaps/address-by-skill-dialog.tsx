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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { GapView } from '@/lib/api/types';
import { useProjectSkills } from '@/lib/api/queries/use-skills';
import { useAddressGapBySkill } from '@/lib/api/queries/use-gaps';

interface AddressBySkillDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectSlug: string;
  gap: GapView | null;
}

export function AddressBySkillDialog({
  open,
  onOpenChange,
  projectSlug,
  gap,
}: AddressBySkillDialogProps) {
  const [skillSlug, setSkillSlug] = useState<string>('');
  const [rationale, setRationale] = useState('');

  const { data: skills, isLoading: skillsLoading } = useProjectSkills(
    projectSlug,
    open
  );
  const addressMutation = useAddressGapBySkill(projectSlug);

  useEffect(() => {
    if (!open) {
      setSkillSlug('');
      setRationale('');
    }
  }, [open]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!gap || !skillSlug) return;
    addressMutation.mutate(
      {
        gapId: gap.id,
        payload: {
          skill_slug: skillSlug,
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
            <DialogTitle>Address by skill</DialogTitle>
            <DialogDescription>
              {gap ? (
                <>Pick the existing skill that covers <strong>{gap.title}</strong>.</>
              ) : (
                'Pick the existing skill that covers this gap.'
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="skill-select">Skill</Label>
              <Select value={skillSlug} onValueChange={setSkillSlug}>
                <SelectTrigger id="skill-select">
                  <SelectValue
                    placeholder={
                      skillsLoading ? 'Loading skills…' : 'Select a skill'
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {(skills ?? []).map((skill) => (
                    <SelectItem key={skill.slug} value={skill.slug}>
                      {skill.name}
                    </SelectItem>
                  ))}
                  {!skillsLoading && (skills?.length ?? 0) === 0 && (
                    <SelectItem value="__none" disabled>
                      No skills in this project yet
                    </SelectItem>
                  )}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="rationale">Rationale (optional)</Label>
              <Textarea
                id="rationale"
                value={rationale}
                onChange={(e) => setRationale(e.target.value)}
                placeholder="Why does this skill cover the gap?"
                rows={3}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={addressMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!skillSlug || addressMutation.isPending}
            >
              {addressMutation.isPending ? 'Saving…' : 'Address gap'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
