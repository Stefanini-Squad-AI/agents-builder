'use client';

import { useCallback, useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import { Sparkles, ArrowLeft, AlertCircle, Loader2, Wand2, CheckCircle2, RefreshCw, Clock } from 'lucide-react';
import { SkillGrid, ProposeSkillsDialog } from '@/components/skills';
import { useWorkerStatus } from '@/lib/api/queries/use-system';
import {
  useProjectSkills,
  useSkillStats,
  useProposeSkills,
  useBulkCreateSkills,
  useDeleteSkill,
  useDraftAllSkills,
} from '@/lib/api/queries/use-skills';
import { SkillView, ProposedSkill, SkillKind } from '@/lib/api/types';

interface SkillsPageProps {
  params: {
    slug: string;
  };
}

export default function SkillsPage({ params }: SkillsPageProps) {
  const { slug: projectSlug } = params;
  const router = useRouter();

  // State
  const [isProposeDialogOpen, setIsProposeDialogOpen] = useState(false);
  const [deletingSkillSlug, setDeletingSkillSlug] = useState<string | null>(null);
  const [draftAllMessage, setDraftAllMessage] = useState<string | null>(null);
  const [isDraftingInProgress, setIsDraftingInProgress] = useState(false);
  const [previousWithContent, setPreviousWithContent] = useState<number | null>(null);

  // Worker status for real-time updates
  const { status: workerStatus } = useWorkerStatus(isDraftingInProgress, 3000);

  // Queries - poll every 3s when drafting is in progress
  const {
    data: skills,
    isLoading: isLoadingSkills,
    error: skillsError,
    refetch: refetchSkills,
  } = useProjectSkills(projectSlug, true, isDraftingInProgress ? 3000 : 0);

  const { data: stats, refetch: refetchStats } = useSkillStats(
    projectSlug,
    true,
    isDraftingInProgress ? 3000 : 0
  );

  // Track drafting progress
  useEffect(() => {
    if (stats && isDraftingInProgress) {
      // Check if more skills now have content
      if (previousWithContent !== null && stats.with_content > previousWithContent) {
        // A skill was just drafted!
        setDraftAllMessage(
          `Drafting in progress: ${stats.with_content}/${stats.total_skills} completed`
        );
      }
      setPreviousWithContent(stats.with_content);

      // Stop polling when all skills are done (no pending or drafting left)
      const pendingCount = stats.by_draft_status?.pending ?? 0;
      const draftingCount = stats.by_draft_status?.drafting ?? 0;
      const errorCount = stats.by_draft_status?.error ?? 0;

      if (pendingCount === 0 && draftingCount === 0) {
        setIsDraftingInProgress(false);
        if (errorCount > 0) {
          setDraftAllMessage(
            `Drafting complete: ${stats.with_content}/${stats.total_skills} succeeded, ${errorCount} failed`
          );
        } else {
          setDraftAllMessage(`All ${stats.total_skills} skill(s) drafted successfully!`);
        }
        setTimeout(() => setDraftAllMessage(null), 5000);
      }
    }
  }, [stats, isDraftingInProgress, previousWithContent]);

  // Also stop polling if worker has no pending jobs and we were drafting
  useEffect(() => {
    if (isDraftingInProgress && workerStatus && workerStatus.pending_jobs === 0) {
      // Give it a moment for final updates
      setTimeout(() => {
        refetchSkills();
        refetchStats();
        setIsDraftingInProgress(false);
      }, 2000);
    }
  }, [workerStatus, isDraftingInProgress, refetchSkills, refetchStats]);

  // Mutations
  const proposeSkillsMutation = useProposeSkills(projectSlug);
  const bulkCreateMutation = useBulkCreateSkills(projectSlug);
  const deleteSkillMutation = useDeleteSkill(projectSlug);
  const draftAllMutation = useDraftAllSkills(projectSlug);

  // Handle skill click (navigate to editor - Step 2.7)
  const handleSkillClick = useCallback(
    (skill: SkillView) => {
      router.push(`/projects/${projectSlug}/skills/${skill.slug}` as any);
    },
    [router, projectSlug]
  );

  // Handle skill edit (same as click for now)
  const handleSkillEdit = useCallback(
    (skill: SkillView) => {
      router.push(`/projects/${projectSlug}/skills/${skill.slug}` as any);
    },
    [router, projectSlug]
  );

  // Handle skill delete
  const handleSkillDelete = useCallback(
    async (skill: SkillView) => {
      setDeletingSkillSlug(skill.slug);
      try {
        await deleteSkillMutation.mutateAsync(skill.slug);
      } finally {
        setDeletingSkillSlug(null);
      }
    },
    [deleteSkillMutation]
  );

  // Handle propose skills
  const handlePropose = useCallback(async () => {
    const result = await proposeSkillsMutation.mutateAsync();
    return result;
  }, [proposeSkillsMutation]);

  // Handle accept proposed skills
  const handleAcceptSkills = useCallback(
    async (selectedSkills: ProposedSkill[]) => {
      await bulkCreateMutation.mutateAsync({
        skills: selectedSkills.map((s) => ({
          slug: s.slug,
          name: s.name,
          description: s.description,
          kind: s.kind,
          rationale: s.rationale,
          body_md: '',
        })),
      });
      // Auto-draft all newly created skills in background
      setPreviousWithContent(0);
      setIsDraftingInProgress(true);
      setDraftAllMessage(`Queued ${selectedSkills.length} skill(s) for drafting. Watching for progress...`);
      await draftAllMutation.mutateAsync({ include_resources: true });
    },
    [bulkCreateMutation, draftAllMutation]
  );

  return (
    <div className="container max-w-6xl py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push(`/projects/${projectSlug}` as any)}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">Skills Library</h1>
            <p className="text-muted-foreground">
              Define reusable skills for AI agents working on your project
            </p>
          </div>
        </div>

        <div className="flex gap-2">
          <Button onClick={() => setIsProposeDialogOpen(true)}>
            <Sparkles className="mr-2 h-4 w-4" />
            Propose Skill Set
          </Button>
          {/* Draft All button - shown when there are undrafted skills */}
          {stats && stats.total_skills > 0 && stats.with_content < stats.total_skills && (
            <Button
              variant="outline"
              onClick={() => {
                setPreviousWithContent(stats?.with_content ?? 0);
                setIsDraftingInProgress(true);
                draftAllMutation.mutate(
                  { include_resources: true },
                  {
                    onSuccess: (data) => {
                      if (data.queued === 0) {
                        setIsDraftingInProgress(false);
                        setDraftAllMessage('All skills already have content.');
                        setTimeout(() => setDraftAllMessage(null), 5000);
                      } else {
                        setDraftAllMessage(
                          `Queued ${data.queued} skill(s) for drafting. Watching for progress...`
                        );
                      }
                    },
                    onError: (error) => {
                      setIsDraftingInProgress(false);
                      setDraftAllMessage(
                        `Failed to queue skills: ${error instanceof Error ? error.message : 'Unknown error'}`
                      );
                      setTimeout(() => setDraftAllMessage(null), 10000);
                    },
                  }
                );
              }}
              disabled={draftAllMutation.isPending || isDraftingInProgress}
            >
              {draftAllMutation.isPending || isDraftingInProgress ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Wand2 className="mr-2 h-4 w-4" />
              )}
              {isDraftingInProgress
                ? `Drafting... (${stats.with_content}/${stats.total_skills})`
                : `Draft All (${stats.total_skills - stats.with_content})`}
            </Button>
          )}
        </div>
      </div>

      {/* Stats */}
      {stats && stats.total_skills > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Statistics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">Total: </span>
                <span className="font-medium">{stats.total_skills}</span>
              </div>
              {Object.entries(stats.by_kind).map(([kind, count]) => (
                <div key={kind} className="flex items-center gap-1">
                  <Badge variant="secondary" className="capitalize">
                    {kind}
                  </Badge>
                  <span className="font-medium">{count}</span>
                </div>
              ))}
              <div>
                <span className="text-muted-foreground">With content: </span>
                <span className="font-medium">
                  {stats.with_content}/{stats.total_skills}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">Completion: </span>
                <span className="font-medium">{stats.completion_percentage.toFixed(0)}%</span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Draft All feedback message */}
      {(draftAllMessage || isDraftingInProgress) && (
        <Alert variant={draftAllMessage?.includes('Failed') ? 'destructive' : 'default'}>
          {draftAllMessage?.includes('Failed') ? (
            <AlertCircle className="h-4 w-4" />
          ) : isDraftingInProgress ? (
            <RefreshCw className="h-4 w-4 animate-spin" />
          ) : (
            <CheckCircle2 className="h-4 w-4" />
          )}
          <AlertTitle>
            {draftAllMessage?.includes('Failed')
              ? 'Error'
              : isDraftingInProgress
              ? 'Drafting Skills'
              : 'Complete'}
          </AlertTitle>
          <AlertDescription className="space-y-2">
            <p>{draftAllMessage}</p>
            {isDraftingInProgress && stats && (
              <div className="space-y-2">
                {/* Draft status breakdown */}
                <div className="flex flex-wrap gap-3 text-xs">
                  {stats.by_draft_status?.pending > 0 && (
                    <div className="flex items-center gap-1 text-blue-600 dark:text-blue-400">
                      <Clock className="h-3 w-3" />
                      <span>{stats.by_draft_status.pending} queued</span>
                    </div>
                  )}
                  {stats.by_draft_status?.drafting > 0 && (
                    <div className="flex items-center gap-1 text-yellow-600 dark:text-yellow-400">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      <span>{stats.by_draft_status.drafting} drafting</span>
                    </div>
                  )}
                  {stats.by_draft_status?.success > 0 && (
                    <div className="flex items-center gap-1 text-green-600 dark:text-green-400">
                      <CheckCircle2 className="h-3 w-3" />
                      <span>{stats.by_draft_status.success} done</span>
                    </div>
                  )}
                  {stats.by_draft_status?.error > 0 && (
                    <div className="flex items-center gap-1 text-red-600 dark:text-red-400">
                      <AlertCircle className="h-3 w-3" />
                      <span>{stats.by_draft_status.error} failed</span>
                    </div>
                  )}
                </div>
                {/* Progress bar */}
                <div className="flex justify-between text-xs">
                  <span>Progress: {stats.with_content}/{stats.total_skills} skills</span>
                  <span>{stats.completion_percentage.toFixed(0)}%</span>
                </div>
                <Progress value={stats.completion_percentage} className="h-2" />
                {workerStatus && (
                  <p className="text-xs text-muted-foreground mt-1">
                    {workerStatus.status === 'healthy' 
                      ? `Worker active, ${workerStatus.pending_jobs} job(s) pending`
                      : workerStatus.status === 'no_workers'
                      ? '⚠️ No workers detected. Start worker to process jobs.'
                      : '❌ Redis unavailable'}
                  </p>
                )}
              </div>
            )}
          </AlertDescription>
        </Alert>
      )}

      {/* Error */}
      {skillsError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error loading skills</AlertTitle>
          <AlertDescription>
            {skillsError instanceof Error ? skillsError.message : 'Unknown error'}
          </AlertDescription>
        </Alert>
      )}

      {/* Skills grid */}
      <SkillGrid
        skills={skills || []}
        projectSlug={projectSlug}
        isLoading={isLoadingSkills}
        onSkillClick={handleSkillClick}
        onSkillEdit={handleSkillEdit}
        onSkillDelete={handleSkillDelete}
        deletingSkillSlug={deletingSkillSlug}
      />

      {/* Propose skills dialog */}
      <ProposeSkillsDialog
        open={isProposeDialogOpen}
        onOpenChange={setIsProposeDialogOpen}
        onPropose={handlePropose}
        onAccept={handleAcceptSkills}
      />
    </div>
  );
}
