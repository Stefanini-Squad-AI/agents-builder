'use client';

import { useState, useCallback } from 'react';
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
import { Checkbox } from '@/components/ui/checkbox';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  Loader2,
  Sparkles,
  BookOpen,
  Code2,
  Search,
  ListChecks,
  FileText,
  AlertCircle,
  CheckCircle2,
  Info,
} from 'lucide-react';
import { ProposedSkill, SkillKind } from '@/lib/api/types';
import { cn } from '@/lib/utils';

interface ProposeSkillsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPropose: () => Promise<{
    skills: ProposedSkill[];
    coverage_notes: string;
    gaps: string[];
    llm_run_id: string;
  }>;
  onAccept: (skills: ProposedSkill[]) => Promise<void>;
}

/**
 * Get icon for skill kind
 */
function getKindIcon(kind: SkillKind) {
  switch (kind) {
    case SkillKind.CONTEXT:
      return BookOpen;
    case SkillKind.ANALYZER:
      return Search;
    case SkillKind.AUTHORING:
      return Code2;
    case SkillKind.PROCEDURE:
      return ListChecks;
    default:
      return FileText;
  }
}

/**
 * Get color for skill kind
 */
function getKindColor(kind: SkillKind): string {
  switch (kind) {
    case SkillKind.CONTEXT:
      return 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300';
    case SkillKind.ANALYZER:
      return 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300';
    case SkillKind.AUTHORING:
      return 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300';
    case SkillKind.PROCEDURE:
      return 'bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300';
    default:
      return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300';
  }
}

type DialogState = 'idle' | 'proposing' | 'proposed' | 'accepting' | 'error';

/**
 * Dialog for proposing and accepting skills from LLM
 */
export function ProposeSkillsDialog({
  open,
  onOpenChange,
  onPropose,
  onAccept,
}: ProposeSkillsDialogProps) {
  const [state, setState] = useState<DialogState>('idle');
  const [error, setError] = useState<string | null>(null);
  const [proposedSkills, setProposedSkills] = useState<ProposedSkill[]>([]);
  const [coverageNotes, setCoverageNotes] = useState<string>('');
  const [gaps, setGaps] = useState<string[]>([]);
  const [selectedSlugs, setSelectedSlugs] = useState<Set<string>>(new Set());

  // Reset state when dialog closes
  const handleOpenChange = useCallback((newOpen: boolean) => {
    if (!newOpen) {
      // Reset state after animation
      setTimeout(() => {
        setState('idle');
        setError(null);
        setProposedSkills([]);
        setCoverageNotes('');
        setGaps([]);
        setSelectedSlugs(new Set());
      }, 200);
    }
    onOpenChange(newOpen);
  }, [onOpenChange]);

  // Handle propose action
  const handlePropose = useCallback(async () => {
    setState('proposing');
    setError(null);

    try {
      const result = await onPropose();
      setProposedSkills(result.skills);
      setCoverageNotes(result.coverage_notes);
      setGaps(result.gaps);
      // Select all skills by default
      setSelectedSlugs(new Set(result.skills.map((s) => s.slug)));
      setState('proposed');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to propose skills');
      setState('error');
    }
  }, [onPropose]);

  // Handle skill selection toggle
  const handleToggleSkill = useCallback((slug: string) => {
    setSelectedSlugs((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) {
        next.delete(slug);
      } else {
        next.add(slug);
      }
      return next;
    });
  }, []);

  // Handle select all / none
  const handleSelectAll = useCallback(() => {
    if (selectedSlugs.size === proposedSkills.length) {
      setSelectedSlugs(new Set());
    } else {
      setSelectedSlugs(new Set(proposedSkills.map((s) => s.slug)));
    }
  }, [proposedSkills, selectedSlugs]);

  // Handle accept selected skills
  const handleAccept = useCallback(async () => {
    const selectedSkills = proposedSkills.filter((s) => selectedSlugs.has(s.slug));
    if (selectedSkills.length === 0) return;

    setState('accepting');
    setError(null);

    try {
      await onAccept(selectedSkills);
      handleOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create skills');
      setState('error');
    }
  }, [proposedSkills, selectedSlugs, onAccept, handleOpenChange]);

  const isLoading = state === 'proposing' || state === 'accepting';
  const hasProposals = proposedSkills.length > 0;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-3xl h-[90vh] flex flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            Propose Skill Set
          </DialogTitle>
          <DialogDescription>
            {state === 'idle' && 'Generate skill suggestions based on your project context.'}
            {state === 'proposing' && 'Analyzing your project and generating skill suggestions...'}
            {state === 'proposed' && `Select which skills to add to your project.`}
            {state === 'accepting' && 'Creating selected skills...'}
            {state === 'error' && 'An error occurred. Try again.'}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 min-h-0 overflow-hidden">
          {/* Initial state */}
          {state === 'idle' && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="p-4 rounded-full bg-primary/10 mb-4">
                <Sparkles className="h-8 w-8 text-primary" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Ready to generate skills</h3>
              <p className="text-muted-foreground max-w-md mb-6">
                The AI will analyze your project objective, Q&A answers, tech choices, and
                uploaded artifacts to suggest 5-10 relevant skills.
              </p>
              <Button onClick={handlePropose}>
                <Sparkles className="mr-2 h-4 w-4" />
                Generate Suggestions
              </Button>
            </div>
          )}

          {/* Loading state */}
          {state === 'proposing' && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Loader2 className="h-12 w-12 animate-spin text-primary mb-4" />
              <h3 className="text-lg font-semibold mb-2">Generating skill suggestions</h3>
              <p className="text-muted-foreground">
                This may take 10-30 seconds...
              </p>
            </div>
          )}

          {/* Error state */}
          {state === 'error' && error && (
            <div className="py-8">
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Error</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
              <div className="flex justify-center mt-6">
                <Button onClick={handlePropose}>
                  Try Again
                </Button>
              </div>
            </div>
          )}

          {/* Proposed skills */}
          {(state === 'proposed' || state === 'accepting') && hasProposals && (
            <div className="flex flex-col h-full min-h-0 space-y-4">
              {/* Coverage notes */}
              {coverageNotes && (
                <Alert className="shrink-0">
                  <Info className="h-4 w-4" />
                  <AlertTitle>Coverage</AlertTitle>
                  <AlertDescription>{coverageNotes}</AlertDescription>
                </Alert>
              )}

              {/* Gaps warning */}
              {gaps.length > 0 && (
                <Alert variant="destructive" className="shrink-0">
                  <AlertCircle className="h-4 w-4" />
                  <AlertTitle>Potential Gaps</AlertTitle>
                  <AlertDescription>
                    <ul className="list-disc list-inside">
                      {gaps.map((gap, i) => (
                        <li key={i}>{gap}</li>
                      ))}
                    </ul>
                  </AlertDescription>
                </Alert>
              )}

              {/* Select all toggle */}
              <div className="flex items-center justify-between shrink-0">
                <span className="text-sm text-muted-foreground">
                  {selectedSlugs.size} of {proposedSkills.length} selected
                </span>
                <Button variant="ghost" size="sm" onClick={handleSelectAll}>
                  {selectedSlugs.size === proposedSkills.length ? 'Deselect all' : 'Select all'}
                </Button>
              </div>

              {/* Skills list */}
              <ScrollArea className="flex-1 min-h-[200px] max-h-[45vh] border rounded-lg overflow-hidden">
                <div className="p-4 space-y-3">
                  {proposedSkills.map((skill) => {
                    const KindIcon = getKindIcon(skill.kind);
                    const isSelected = selectedSlugs.has(skill.slug);

                    return (
                      <div
                        key={skill.slug}
                        className={cn(
                          'flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors',
                          isSelected
                            ? 'bg-primary/5 border-primary/30'
                            : 'hover:bg-muted/50'
                        )}
                        onClick={() => handleToggleSkill(skill.slug)}
                      >
                        <Checkbox
                          checked={isSelected}
                          onCheckedChange={() => handleToggleSkill(skill.slug)}
                          className="mt-1"
                        />
                        <div className={cn('p-2 rounded-lg shrink-0', getKindColor(skill.kind))}>
                          <KindIcon className="h-4 w-4" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{skill.name}</span>
                            <Badge
                              variant="secondary"
                              className={cn('text-xs capitalize', getKindColor(skill.kind))}
                            >
                              {skill.kind}
                            </Badge>
                          </div>
                          <p className="text-sm text-muted-foreground mt-1">
                            {skill.description}
                          </p>
                          {skill.rationale && (
                            <p className="text-xs text-muted-foreground mt-2 italic">
                              Rationale: {skill.rationale}
                            </p>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </ScrollArea>
            </div>
          )}
        </div>

        <DialogFooter className="shrink-0 border-t pt-4 mt-4 bg-background">
          {state === 'proposed' && (
            <>
              <Button variant="outline" onClick={() => handleOpenChange(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleAccept}
                disabled={selectedSlugs.size === 0}
              >
                <CheckCircle2 className="mr-2 h-4 w-4" />
                Add {selectedSlugs.size} Skill{selectedSlugs.size !== 1 ? 's' : ''}
              </Button>
            </>
          )}
          {state === 'accepting' && (
            <Button disabled>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Creating skills...
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default ProposeSkillsDialog;
