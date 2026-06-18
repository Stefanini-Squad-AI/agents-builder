'use client';

import { useParams, useRouter } from 'next/navigation';
import { useState } from 'react';
import { usePhases, useCardsStats, useProposeBacklog } from '@/lib/api/queries';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { PhaseAccordion } from '@/components/backlog/phase-accordion';
import { ProposeBacklogDialog } from '@/components/backlog/propose-backlog-dialog';
import { ArrowLeft, Sparkles, Loader2, LayoutList, Layers, Target } from 'lucide-react';

export default function BacklogPage() {
  const params = useParams();
  const router = useRouter();
  const projectSlug = params.slug as string;

  // Fetch phases and stats
  const { data: phases, isLoading: phasesLoading, error: phasesError } = usePhases(projectSlug);
  const { data: stats, isLoading: statsLoading } = useCardsStats(projectSlug);

  // Propose backlog mutation
  const proposeBacklog = useProposeBacklog(projectSlug);

  // Dialog state
  const [proposeDialogOpen, setProposeDialogOpen] = useState(false);

  // Calculate totals
  const totalPhases = phases?.length || 0;
  const totalCards = stats?.total || 0;
  const totalStoryPoints = stats?.total_story_points || 0;

  const handleProposeBacklog = async () => {
    try {
      await proposeBacklog.mutateAsync();
      setProposeDialogOpen(false);
    } catch (error) {
      console.error('Failed to propose backlog:', error);
    }
  };

  if (phasesLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (phasesError) {
    return (
      <div className="flex flex-col items-center justify-center h-[50vh] gap-4">
        <p className="text-muted-foreground">Failed to load backlog</p>
        <Button variant="outline" onClick={() => router.back()}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Go Back
        </Button>
      </div>
    );
  }

  const hasBacklog = totalPhases > 0;

  return (
    <div className="container mx-auto py-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push(`/projects/${projectSlug}` as any)}
          >
            <ArrowLeft className="h-4 w-4 sm:mr-2" />
            <span className="hidden sm:inline">Back to Project</span>
          </Button>
          <div className="hidden sm:block h-6 w-px bg-border" />
          <h1 className="text-xl sm:text-2xl font-bold">Backlog</h1>
        </div>
        <Button
          onClick={() => setProposeDialogOpen(true)}
          disabled={proposeBacklog.isPending}
          className="w-full sm:w-auto"
        >
          {proposeBacklog.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Sparkles className="mr-2 h-4 w-4" />
          )}
          Propose Backlog
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Phases</CardTitle>
            <Layers className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalPhases}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cards</CardTitle>
            <LayoutList className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalCards}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Story Points</CardTitle>
            <Target className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalStoryPoints}</div>
          </CardContent>
        </Card>
      </div>

      {/* Backlog content */}
      {!hasBacklog ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <Layers className="h-16 w-16 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No backlog yet</h3>
            <p className="text-muted-foreground text-center mb-6 max-w-md">
              Your backlog is empty. Click &quot;Propose Backlog&quot; to have AI generate
              phases and cards based on your project skills and context.
            </p>
            <Button onClick={() => setProposeDialogOpen(true)}>
              <Sparkles className="mr-2 h-4 w-4" />
              Propose Backlog
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {phases?.map((phase) => (
            <PhaseAccordion
              key={phase.id}
              phase={phase}
              projectSlug={projectSlug}
            />
          ))}
        </div>
      )}

      {/* Propose Dialog */}
      <ProposeBacklogDialog
        open={proposeDialogOpen}
        onOpenChange={setProposeDialogOpen}
        onConfirm={handleProposeBacklog}
        isPending={proposeBacklog.isPending}
        hasExistingBacklog={hasBacklog}
      />
    </div>
  );
}
