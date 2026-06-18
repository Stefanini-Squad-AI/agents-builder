'use client';

import { useState, useCallback, useMemo } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  Plus, 
  HelpCircle, 
  Sparkles, 
  Target,
  Clock,
  CircleDot,
  Ban,
  CheckCircle2,
  Circle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { TechChip } from './tech-chip';
import { TechChoiceRole, TechChoiceSource, TechItemView, TechChoiceView } from '@/lib/api/types';

interface DimensionCardProps {
  dimensionSlug: string;
  dimensionName: string;
  description?: string;
  items: TechItemView[];
  choices: TechChoiceView[];
  onSelectItem: (itemSlug: string, role: TechChoiceRole) => void;
  onDeselectItem: (itemSlug: string) => void;
  onMarkTbd: () => void;
  onClearTbd: () => void;
  onAddCustom: () => void;
  onSuggestAi?: () => void;
  onAcceptSuggestion: (itemSlug: string) => void;
  onDismissSuggestion: (itemSlug: string) => void;
  isLoading?: boolean;
  isSuggestingAi?: boolean;
}

const roleOptions: { value: TechChoiceRole; label: string; icon: typeof Target; color: string }[] = [
  { value: TechChoiceRole.TARGET, label: 'Target', icon: Target, color: 'text-green-600' },
  { value: TechChoiceRole.LEGACY, label: 'Legacy', icon: Clock, color: 'text-amber-600' },
  { value: TechChoiceRole.OPTIONAL, label: 'Optional', icon: CircleDot, color: 'text-blue-600' },
  { value: TechChoiceRole.MUST_AVOID, label: 'Must Avoid', icon: Ban, color: 'text-red-600' },
];

/**
 * Dimension card component showing a tech dimension with its items and choices.
 * Includes chip picker, role selection, TBD marking, custom items, and AI suggestions.
 */
export function DimensionCard({
  dimensionSlug,
  dimensionName,
  description,
  items,
  choices,
  onSelectItem,
  onDeselectItem,
  onMarkTbd,
  onClearTbd,
  onAddCustom,
  onSuggestAi,
  onAcceptSuggestion,
  onDismissSuggestion,
  isLoading,
  isSuggestingAi,
}: DimensionCardProps) {
  const [selectedRole, setSelectedRole] = useState<TechChoiceRole>(TechChoiceRole.TARGET);

  // Build a set of selected item slugs for quick lookup
  const selectedSlugs = useMemo(() => {
    return new Set(
      choices
        .filter(c => c.accepted !== false) // Exclude pending suggestions
        .map(c => c.tech_item_slug)
        .filter(Boolean) as string[]
    );
  }, [choices]);

  // Get pending suggestions
  const pendingSuggestions = useMemo(() => {
    return choices.filter(
      c => c.source === TechChoiceSource.LLM_SUGGESTED && !c.accepted
    );
  }, [choices]);

  // Check if TBD is marked
  const hasTbd = useMemo(() => {
    return choices.some(c => c.role === TechChoiceRole.TBD);
  }, [choices]);

  // Get accepted choices count (excluding TBD)
  const acceptedCount = useMemo(() => {
    return choices.filter(
      c => c.role !== TechChoiceRole.TBD && c.accepted !== false
    ).length;
  }, [choices]);

  // Handle item selection with role
  const handleSelectItem = useCallback((itemSlug: string) => {
    onSelectItem(itemSlug, selectedRole);
  }, [onSelectItem, selectedRole]);

  // Get choice for a specific item
  const getChoiceForItem = useCallback((itemSlug: string) => {
    return choices.find(c => c.tech_item_slug === itemSlug);
  }, [choices]);

  // Sort items: selected first, then alphabetically
  const sortedItems = useMemo(() => {
    return [...items].sort((a, b) => {
      const aSelected = selectedSlugs.has(a.slug);
      const bSelected = selectedSlugs.has(b.slug);
      if (aSelected && !bSelected) return -1;
      if (!aSelected && bSelected) return 1;
      return a.name.localeCompare(b.name);
    });
  }, [items, selectedSlugs]);

  return (
    <Card className={cn(
      'transition-all',
      acceptedCount > 0 && 'border-green-200 dark:border-green-800',
      hasTbd && acceptedCount === 0 && 'border-amber-200 dark:border-amber-800'
    )}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-2">
            {/* Status icon */}
            {acceptedCount > 0 ? (
              <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400 shrink-0 mt-0.5" />
            ) : hasTbd ? (
              <HelpCircle className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            ) : (
              <Circle className="h-5 w-5 text-muted-foreground shrink-0 mt-0.5" />
            )}
            
            <div>
              <CardTitle className="text-base font-medium">{dimensionName}</CardTitle>
              {description && (
                <CardDescription className="mt-1 text-sm">
                  {description}
                </CardDescription>
              )}
            </div>
          </div>

          {/* Stats badges */}
          <div className="flex items-center gap-2 shrink-0">
            {acceptedCount > 0 && (
              <Badge variant="secondary" className="text-xs">
                {acceptedCount} selected
              </Badge>
            )}
            {pendingSuggestions.length > 0 && (
              <Badge className="bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300 text-xs">
                <Sparkles className="h-3 w-3 mr-1" />
                {pendingSuggestions.length} suggested
              </Badge>
            )}
            {hasTbd && (
              <Badge variant="outline" className="text-xs">
                TBD
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Pending AI suggestions */}
        {pendingSuggestions.length > 0 && (
          <div className="p-3 rounded-lg bg-purple-50 dark:bg-purple-950 border border-purple-200 dark:border-purple-800">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="h-4 w-4 text-purple-500" />
              <span className="text-sm font-medium text-purple-700 dark:text-purple-300">
                AI Suggestions
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {pendingSuggestions.map(suggestion => (
                <TechChip
                  key={suggestion.id}
                  itemSlug={suggestion.tech_item_slug || ''}
                  itemName={suggestion.tech_item_name || 'Unknown'}
                  isSelected={false}
                  source={TechChoiceSource.LLM_SUGGESTED}
                  accepted={false}
                  confidence={suggestion.llm_confidence}
                  onAccept={() => onAcceptSuggestion(suggestion.tech_item_slug || '')}
                  onDismiss={() => onDismissSuggestion(suggestion.tech_item_slug || '')}
                  disabled={isLoading}
                />
              ))}
            </div>
          </div>
        )}

        {/* Role selector - inline buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm text-muted-foreground">Select as:</span>
          <div className="inline-flex rounded-md border border-input bg-background">
            {roleOptions.map((option, idx) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setSelectedRole(option.value)}
                className={cn(
                  'inline-flex items-center gap-1 px-2.5 py-1.5 text-sm font-medium transition-colors',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  idx === 0 && 'rounded-l-md',
                  idx === roleOptions.length - 1 && 'rounded-r-md',
                  idx !== roleOptions.length - 1 && 'border-r border-input',
                  selectedRole === option.value
                    ? 'bg-accent text-accent-foreground'
                    : 'hover:bg-muted text-muted-foreground hover:text-foreground'
                )}
              >
                <option.icon className={cn('h-3.5 w-3.5', option.color)} />
                <span className="hidden sm:inline">{option.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Item chips */}
        <div className="flex flex-wrap gap-2">
          {sortedItems.map(item => {
            const choice = getChoiceForItem(item.slug);
            const isSelected = selectedSlugs.has(item.slug);
            
            return (
              <TechChip
                key={item.id}
                itemSlug={item.slug}
                itemName={item.name}
                isSelected={isSelected}
                role={choice?.role as TechChoiceRole}
                source={choice?.source as TechChoiceSource}
                accepted={choice?.accepted}
                isCustom={item.is_custom}
                onSelect={() => handleSelectItem(item.slug)}
                onDeselect={() => onDeselectItem(item.slug)}
                disabled={isLoading}
              />
            );
          })}
        </div>

        {/* Action buttons */}
        <div className="flex flex-wrap gap-2 pt-2 border-t">
          <Button
            variant="outline"
            size="sm"
            onClick={onAddCustom}
            disabled={isLoading}
          >
            <Plus className="h-4 w-4 mr-1" />
            Add Custom
          </Button>
          
          {hasTbd ? (
            <Button
              variant="outline"
              size="sm"
              onClick={onClearTbd}
              disabled={isLoading}
            >
              <HelpCircle className="h-4 w-4 mr-1" />
              Clear TBD
            </Button>
          ) : (
            <Button
              variant="outline"
              size="sm"
              onClick={onMarkTbd}
              disabled={isLoading}
            >
              <HelpCircle className="h-4 w-4 mr-1" />
              Mark TBD
            </Button>
          )}
          
          {onSuggestAi && (
            <Button
              variant="outline"
              size="sm"
              onClick={onSuggestAi}
              disabled={isLoading || isSuggestingAi}
            >
              <Sparkles className="h-4 w-4 mr-1" />
              {isSuggestingAi ? 'Suggesting...' : 'Suggest with AI'}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default DimensionCard;
