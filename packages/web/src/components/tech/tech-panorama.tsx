'use client';

import { useState, useCallback, useMemo } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { 
  CheckCircle2, 
  AlertTriangle, 
  ChevronRight,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import { DimensionCard } from './dimension-card';
import { AddCustomDialog } from './add-custom-dialog';
import { 
  useDimensionsWithChoices, 
  useSetTechChoice, 
  useRemoveTechChoice,
  useMarkTbd,
  useClearTbd,
  useAddCustomItem,
  useAcceptSuggestion,
  useDismissSuggestion,
  useTechStats,
} from '@/lib/api/queries/use-tech';
import { TechChoiceRole } from '@/lib/api/types';

interface TechPanoramaProps {
  projectSlug: string;
  onContinue?: () => void;
  showContinueButton?: boolean;
}

/**
 * Full Tech Panorama UI showing all dimensions with their tech choices.
 * Main component for Step 3 of the project wizard.
 */
export function TechPanorama({
  projectSlug,
  onContinue,
  showContinueButton = true,
}: TechPanoramaProps) {
  // Dialog state
  const [customDialogOpen, setCustomDialogOpen] = useState(false);
  const [activeDimension, setActiveDimension] = useState<{
    slug: string;
    name: string;
  } | null>(null);

  // Queries
  const { 
    data: dimensions, 
    isLoading: isDimensionsLoading, 
    error: dimensionsError,
    refetch: refetchDimensions,
  } = useDimensionsWithChoices(projectSlug);
  
  const { 
    data: stats,
    isLoading: isStatsLoading,
  } = useTechStats(projectSlug);

  // Mutations
  const setChoice = useSetTechChoice(projectSlug);
  const removeChoice = useRemoveTechChoice(projectSlug);
  const markTbd = useMarkTbd(projectSlug);
  const clearTbd = useClearTbd(projectSlug);
  const addCustom = useAddCustomItem(projectSlug);
  const acceptSuggestion = useAcceptSuggestion(projectSlug);
  const dismissSuggestion = useDismissSuggestion(projectSlug);

  // Calculate progress
  const progress = useMemo(() => {
    if (!stats) return { answered: 0, total: 0, percent: 0 };
    const answered = stats.covered_dimensions;
    const total = stats.total_dimensions;
    return {
      answered,
      total,
      percent: total > 0 ? Math.round((answered / total) * 100) : 0,
    };
  }, [stats]);

  // Event handlers
  const handleSelectItem = useCallback(
    async (dimensionSlug: string, itemSlug: string, role: TechChoiceRole) => {
      await setChoice.mutateAsync({ dimensionSlug, itemSlug, role });
    },
    [setChoice]
  );

  const handleDeselectItem = useCallback(
    async (dimensionSlug: string, itemSlug: string) => {
      await removeChoice.mutateAsync({ dimensionSlug, itemSlug });
    },
    [removeChoice]
  );

  const handleMarkTbd = useCallback(
    async (dimensionSlug: string) => {
      await markTbd.mutateAsync({ dimensionSlug });
    },
    [markTbd]
  );

  const handleClearTbd = useCallback(
    async (dimensionSlug: string) => {
      await clearTbd.mutateAsync(dimensionSlug);
    },
    [clearTbd]
  );

  const handleOpenCustomDialog = useCallback((slug: string, name: string) => {
    setActiveDimension({ slug, name });
    setCustomDialogOpen(true);
  }, []);

  const handleAddCustom = useCallback(
    async (data: {
      name: string;
      description?: string;
      role: TechChoiceRole;
      tags?: string[];
      notes?: string;
    }) => {
      if (!activeDimension) return;
      
      await addCustom.mutateAsync({
        dimensionSlug: activeDimension.slug,
        name: data.name,
        description: data.description,
        role: data.role,
        tags: data.tags,
        notes: data.notes,
      });
    },
    [activeDimension, addCustom]
  );

  const handleAcceptSuggestion = useCallback(
    async (dimensionSlug: string, itemSlug: string) => {
      await acceptSuggestion.mutateAsync({ dimensionSlug, itemSlug });
    },
    [acceptSuggestion]
  );

  const handleDismissSuggestion = useCallback(
    async (dimensionSlug: string, itemSlug: string) => {
      await dismissSuggestion.mutateAsync({ dimensionSlug, itemSlug });
    },
    [dismissSuggestion]
  );

  // Check for mutation loading state
  const isMutating = 
    setChoice.isPending || 
    removeChoice.isPending || 
    markTbd.isPending || 
    clearTbd.isPending || 
    addCustom.isPending ||
    acceptSuggestion.isPending ||
    dismissSuggestion.isPending;

  // Loading state
  if (isDimensionsLoading) {
    return (
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-4 w-96 mt-2" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-2 w-full" />
          </CardContent>
        </Card>
        <div className="grid gap-4 md:grid-cols-2">
          {[1, 2, 3, 4].map(i => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-5 w-32" />
                <Skeleton className="h-4 w-full mt-2" />
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {[1, 2, 3, 4, 5].map(j => (
                    <Skeleton key={j} className="h-8 w-20 rounded-full" />
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  // Error state
  if (dimensionsError) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>Error loading tech dimensions</AlertTitle>
        <AlertDescription className="mt-2">
          <p className="mb-2">
            {dimensionsError instanceof Error 
              ? dimensionsError.message 
              : 'Failed to load tech stack options'}
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetchDimensions()}
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Try Again
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      {/* Progress Header */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">Tech Stack Discovery</CardTitle>
              <CardDescription>
                Select technologies for each dimension. Mark as TBD if undecided.
              </CardDescription>
            </div>
            <Badge variant="outline" className="text-sm">
              {progress.answered} / {progress.total} dimensions
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <Progress value={progress.percent} className="h-2" />
          {progress.answered === 0 && (
            <p className="text-sm text-muted-foreground mt-2">
              No dimensions answered yet. Select technologies or mark as TBD.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Warning if no dimensions answered */}
      {showContinueButton && progress.answered === 0 && (
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>No technologies selected</AlertTitle>
          <AlertDescription>
            You can continue without selections, but AI agents will have less context.
          </AlertDescription>
        </Alert>
      )}

      {/* Dimension Cards Grid */}
      <div className="grid gap-4 md:grid-cols-2">
        {dimensions?.map(dimension => (
          <DimensionCard
            key={dimension.slug}
            dimensionSlug={dimension.slug}
            dimensionName={dimension.name}
            description={dimension.description}
            items={dimension.items}
            choices={dimension.choices}
            onSelectItem={(itemSlug, role) => 
              handleSelectItem(dimension.slug, itemSlug, role)
            }
            onDeselectItem={(itemSlug) => 
              handleDeselectItem(dimension.slug, itemSlug)
            }
            onMarkTbd={() => handleMarkTbd(dimension.slug)}
            onClearTbd={() => handleClearTbd(dimension.slug)}
            onAddCustom={() => 
              handleOpenCustomDialog(dimension.slug, dimension.name)
            }
            onAcceptSuggestion={(itemSlug) => 
              handleAcceptSuggestion(dimension.slug, itemSlug)
            }
            onDismissSuggestion={(itemSlug) => 
              handleDismissSuggestion(dimension.slug, itemSlug)
            }
            isLoading={isMutating}
          />
        ))}
      </div>

      {/* Continue Button */}
      {showContinueButton && (
        <div className="flex justify-end pt-4 border-t">
          <Button
            onClick={onContinue}
            disabled={isMutating}
            className="gap-2"
          >
            {isMutating && <Loader2 className="h-4 w-4 animate-spin" />}
            {progress.answered === progress.total ? (
              <>
                <CheckCircle2 className="h-4 w-4" />
                Continue to Preview
              </>
            ) : (
              <>
                Continue
                <ChevronRight className="h-4 w-4" />
              </>
            )}
          </Button>
        </div>
      )}

      {/* Add Custom Dialog */}
      {activeDimension && (
        <AddCustomDialog
          open={customDialogOpen}
          onOpenChange={setCustomDialogOpen}
          dimensionName={activeDimension.name}
          dimensionSlug={activeDimension.slug}
          onSubmit={handleAddCustom}
          isSubmitting={addCustom.isPending}
        />
      )}
    </div>
  );
}

export default TechPanorama;
