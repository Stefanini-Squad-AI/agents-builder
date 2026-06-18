'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import {
  ArrowLeft,
  Plus,
  AlertCircle,
  AlertOctagon,
  Loader2,
} from 'lucide-react';
import { useProject } from '@/lib/api/queries/use-projects';
import { useProjectGaps, useGapsStats } from '@/lib/api/queries/use-gaps';
import { useMcpConfigs } from '@/lib/api/queries/use-mcp';
import {
  GapsStatsStrip,
  GapFilterChips,
  type GapFilterValue,
  GapRow,
  AddGapDialog,
  AddressBySkillDialog,
  CoverByMcpDialog,
  OutOfScopeDialog,
} from '@/components/gaps';
import { GapView, GapStatus } from '@/lib/api/types';

interface GapsPageProps {
  params: { slug: string };
}

export default function GapsPage({ params }: GapsPageProps) {
  const projectSlug = params.slug;
  const router = useRouter();

  const [filter, setFilter] = useState<GapFilterValue>('all');
  const [addOpen, setAddOpen] = useState(false);
  const [addressTarget, setAddressTarget] = useState<GapView | null>(null);
  const [coverTarget, setCoverTarget] = useState<GapView | null>(null);
  const [oosTarget, setOosTarget] = useState<GapView | null>(null);

  const { data: project } = useProject(projectSlug);
  const { data: stats, isLoading: statsLoading } = useGapsStats(projectSlug);
  const statusFilter = filter === 'all' ? undefined : (filter as GapStatus);
  const {
    data: gaps,
    isLoading: gapsLoading,
    error: gapsError,
  } = useProjectGaps(projectSlug, statusFilter);

  // Used to detect "MCP not configured" warnings
  const { data: mcpConfigs } = useMcpConfigs(project?.id ?? '', false, !!project?.id);

  const sortedGaps = useMemo(() => {
    if (!gaps) return [];
    // Open first, then by created_at desc
    return [...gaps].sort((a, b) => {
      if (a.status === 'open' && b.status !== 'open') return -1;
      if (a.status !== 'open' && b.status === 'open') return 1;
      return (
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
    });
  }, [gaps]);

  return (
    <div className="container mx-auto space-y-6 py-6">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-4">
        <Button variant="ghost" size="sm" asChild>
          <Link href={`/projects/${projectSlug}`}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to project
          </Link>
        </Button>
        <div className="h-6 w-px bg-border" />
        <div className="flex items-center gap-2">
          <AlertOctagon className="h-5 w-5 text-amber-600 dark:text-amber-400" />
          <h1 className="text-xl font-semibold">Coverage gaps</h1>
        </div>
        {project && (
          <span className="text-sm text-muted-foreground">— {project.name}</span>
        )}
        <div className="ml-auto">
          <Button onClick={() => setAddOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Add gap
          </Button>
        </div>
      </div>

      <p className="text-sm text-muted-foreground max-w-3xl">
        Gaps are coverage concerns flagged by the LLM (or added manually) that
        no skill yet handles. Decide for each: cover it with an existing skill,
        bring in an MCP server, or mark it as out of scope.
      </p>

      {/* Stats strip */}
      <GapsStatsStrip stats={stats} isLoading={statsLoading} />

      {/* Filter chips */}
      <GapFilterChips value={filter} onChange={setFilter} stats={stats} />

      {/* List */}
      {gapsError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Failed to load gaps</AlertTitle>
          <AlertDescription>
            {gapsError instanceof Error
              ? gapsError.message
              : 'Unknown error'}
            <Button
              variant="link"
              size="sm"
              className="px-1"
              onClick={() => router.refresh()}
            >
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {gapsLoading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-24 w-full rounded-lg" />
          ))}
        </div>
      ) : sortedGaps.length === 0 ? (
        <EmptyState filter={filter} />
      ) : (
        <div className="space-y-3">
          {sortedGaps.map((gap) => (
            <GapRow
              key={gap.id}
              gap={gap}
              projectSlug={projectSlug}
              mcpConfigs={mcpConfigs}
              onAddressBySkill={setAddressTarget}
              onCoverByMcp={setCoverTarget}
              onMarkOutOfScope={setOosTarget}
            />
          ))}
        </div>
      )}

      {/* Dialogs */}
      <AddGapDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        projectSlug={projectSlug}
      />
      <AddressBySkillDialog
        open={addressTarget !== null}
        onOpenChange={(o) => !o && setAddressTarget(null)}
        projectSlug={projectSlug}
        gap={addressTarget}
      />
      <CoverByMcpDialog
        open={coverTarget !== null}
        onOpenChange={(o) => !o && setCoverTarget(null)}
        projectSlug={projectSlug}
        projectId={project?.id}
        gap={coverTarget}
      />
      <OutOfScopeDialog
        open={oosTarget !== null}
        onOpenChange={(o) => !o && setOosTarget(null)}
        projectSlug={projectSlug}
        gap={oosTarget}
      />
    </div>
  );
}

function EmptyState({ filter }: { filter: GapFilterValue }) {
  const message =
    filter === 'all'
      ? 'No gaps yet. Run ProposeSkillSet to detect them, or add one manually.'
      : `No gaps match the current filter.`;

  return (
    <div className="rounded-lg border border-dashed p-10 text-center">
      <Loader2 className="mx-auto h-6 w-6 text-muted-foreground/40" />
      <p className="mt-3 text-sm text-muted-foreground">{message}</p>
    </div>
  );
}
