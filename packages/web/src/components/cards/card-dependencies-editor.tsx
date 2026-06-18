'use client';

import { useState, useEffect, useCallback } from 'react';
import { useUpdateCardDependencies } from '@/lib/api/queries';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { CardView } from '@/lib/api/types';
import { Loader2, ArrowRight, ArrowLeftRight, Save } from 'lucide-react';

interface CardDependenciesEditorProps {
  projectSlug: string;
  cardId: string;
  currentCard: CardView;
  allCards: CardView[];
}

export function CardDependenciesEditor({
  projectSlug,
  cardId,
  currentCard,
  allCards,
}: CardDependenciesEditorProps) {
  const updateDependencies = useUpdateCardDependencies(projectSlug, cardId);

  // Local state for checkboxes
  const [dependsOnCodes, setDependsOnCodes] = useState<string[]>([]);
  const [parallelWithCodes, setParallelWithCodes] = useState<string[]>([]);
  const [isDirty, setIsDirty] = useState(false);

  // Initialize from current card
  useEffect(() => {
    setDependsOnCodes(currentCard.depends_on_codes || []);
    setParallelWithCodes(currentCard.parallel_with_codes || []);
    setIsDirty(false);
  }, [currentCard]);

  // Get available cards (all except current)
  const availableCards = allCards.filter((card) => card.code !== currentCard.code);

  // Group cards by phase
  const cardsByPhase = availableCards.reduce((acc, card) => {
    const phaseId = card.phase_id;
    if (!acc[phaseId]) {
      acc[phaseId] = [];
    }
    acc[phaseId].push(card);
    return acc;
  }, {} as Record<string, CardView[]>);

  // Handle toggle depends_on
  const toggleDependsOn = useCallback((code: string) => {
    setDependsOnCodes((prev) => {
      const next = prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code];
      setIsDirty(true);
      return next;
    });
    // Remove from parallel if being added to depends
    setParallelWithCodes((prev) => {
      if (prev.includes(code)) {
        return prev.filter((c) => c !== code);
      }
      return prev;
    });
  }, []);

  // Handle toggle parallel_with
  const toggleParallelWith = useCallback((code: string) => {
    setParallelWithCodes((prev) => {
      const next = prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code];
      setIsDirty(true);
      return next;
    });
    // Remove from depends if being added to parallel
    setDependsOnCodes((prev) => {
      if (prev.includes(code)) {
        return prev.filter((c) => c !== code);
      }
      return prev;
    });
  }, []);

  // Handle save
  const handleSave = async () => {
    await updateDependencies.mutateAsync({
      depends_on_codes: dependsOnCodes,
      parallel_with_codes: parallelWithCodes,
    });
    setIsDirty(false);
  };

  if (availableCards.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No other cards available to create dependencies.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Legend */}
      <div className="flex items-center gap-6 text-sm text-muted-foreground border-b pb-4">
        <div className="flex items-center gap-2">
          <ArrowRight className="h-4 w-4" />
          <span>Depends On (must complete before this card)</span>
        </div>
        <div className="flex items-center gap-2">
          <ArrowLeftRight className="h-4 w-4" />
          <span>Parallel With (can run at the same time)</span>
        </div>
      </div>

      {/* Cards list */}
      <div className="space-y-6">
        {Object.entries(cardsByPhase).map(([phaseId, cards]) => (
          <div key={phaseId} className="space-y-2">
            <h4 className="text-sm font-medium text-muted-foreground">
              Phase {cards[0]?.code?.split('-')[0] || phaseId}
            </h4>
            <div className="grid gap-2">
              {cards.map((card) => (
                <div
                  key={card.id}
                  className="flex items-center justify-between p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm text-muted-foreground">{card.code}</span>
                      <span className="font-medium">{card.title}</span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      Type: {card.type} | Status: {card.status}
                    </p>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="flex items-center space-x-2">
                      <Checkbox
                        id={`depends-${card.code}`}
                        checked={dependsOnCodes.includes(card.code)}
                        onCheckedChange={() => toggleDependsOn(card.code)}
                      />
                      <Label
                        htmlFor={`depends-${card.code}`}
                        className="text-sm flex items-center gap-1 cursor-pointer"
                      >
                        <ArrowRight className="h-3 w-3" />
                        Depends
                      </Label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Checkbox
                        id={`parallel-${card.code}`}
                        checked={parallelWithCodes.includes(card.code)}
                        onCheckedChange={() => toggleParallelWith(card.code)}
                      />
                      <Label
                        htmlFor={`parallel-${card.code}`}
                        className="text-sm flex items-center gap-1 cursor-pointer"
                      >
                        <ArrowLeftRight className="h-3 w-3" />
                        Parallel
                      </Label>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Save button */}
      <div className="flex justify-end pt-4 border-t">
        <Button onClick={handleSave} disabled={!isDirty || updateDependencies.isPending}>
          {updateDependencies.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Save className="mr-2 h-4 w-4" />
          )}
          Save Dependencies
        </Button>
      </div>

      {/* Summary */}
      {(dependsOnCodes.length > 0 || parallelWithCodes.length > 0) && (
        <div className="text-sm text-muted-foreground border-t pt-4">
          <div className="flex gap-4">
            {dependsOnCodes.length > 0 && (
              <div>
                <span className="font-medium">Depends on:</span>{' '}
                {dependsOnCodes.join(', ')}
              </div>
            )}
            {parallelWithCodes.length > 0 && (
              <div>
                <span className="font-medium">Parallel with:</span>{' '}
                {parallelWithCodes.join(', ')}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
