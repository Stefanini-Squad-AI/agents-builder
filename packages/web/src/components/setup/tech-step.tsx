'use client';

import { useCallback, useState } from 'react';
import { 
  useDimensionsWithChoices, 
  useSetTechChoice, 
  useRemoveTechChoice,
  useTechStats 
} from '@/lib/api/queries/use-tech';
import { TechItemView, TechChoiceView, TechChoiceRole } from '@/lib/api/types';
import { DimensionWithChoices } from '@/lib/api/endpoints/tech';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Input } from '@/components/ui/input';

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { 
  ChevronLeft, 
  ChevronRight, 
  Loader2, 
  X,
  Search,
  Target,
  Clock,
  CircleDot,
  Ban,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const roleOptions = [
  { value: TechChoiceRole.TARGET, label: 'Target', icon: Target, color: 'text-green-600' },
  { value: TechChoiceRole.LEGACY, label: 'Legacy', icon: Clock, color: 'text-amber-600' },
  { value: TechChoiceRole.OPTIONAL, label: 'Optional', icon: CircleDot, color: 'text-blue-600' },
  { value: TechChoiceRole.MUST_AVOID, label: 'Must Avoid', icon: Ban, color: 'text-red-600' },
];

interface TechStepProps {
  projectSlug: string;
  onNext: () => void;
  onPrev: () => void;
}

export function TechStep({ projectSlug, onNext, onPrev }: TechStepProps) {
  const [searchQuery, setSearchQuery] = useState('');
  
  const { data: dimensions, isLoading } = useDimensionsWithChoices(projectSlug);
  const { data: stats } = useTechStats(projectSlug);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Description */}
      <div className="space-y-2">
        <p className="text-muted-foreground">
          Select the technologies used in your project. This helps the AI generate
          relevant skills and implementation cards.
        </p>
        
        {/* Progress */}
        {stats && (
          <div className="flex items-center gap-4">
            <Progress value={stats.coverage_percentage} className="flex-1" />
            <span className="text-sm text-muted-foreground">
              {stats.covered_dimensions}/{stats.total_dimensions} dimensions covered
            </span>
          </div>
        )}
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search technologies..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* Dimensions */}
      <Accordion type="multiple" className="space-y-2" defaultValue={dimensions?.slice(0, 3).map(d => d.slug)}>
        {dimensions?.map((dimension) => (
          <DimensionSection
            key={dimension.slug}
            dimension={dimension}
            projectSlug={projectSlug}
            searchQuery={searchQuery}
          />
        ))}
      </Accordion>

      {/* Navigation */}
      <div className="flex justify-between pt-4 border-t">
        <Button variant="outline" onClick={onPrev}>
          <ChevronLeft className="mr-2 h-4 w-4" />
          Back
        </Button>
        <Button onClick={onNext}>
          Continue
          <ChevronRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

function DimensionSection({ 
  dimension, 
  projectSlug,
  searchQuery 
}: { 
  dimension: DimensionWithChoices;
  projectSlug: string;
  searchQuery: string;
}) {
  const [selectedRole, setSelectedRole] = useState<TechChoiceRole>(TechChoiceRole.TARGET);
  const setTechChoice = useSetTechChoice(projectSlug);
  const removeTechChoice = useRemoveTechChoice(projectSlug);

  const choiceMap = new Map(
    dimension.choices.map(c => [c.tech_item_slug, c])
  );

  // Filter items by search query
  const filteredItems = dimension.items.filter(item => 
    !searchQuery || 
    item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    item.slug.toLowerCase().includes(searchQuery.toLowerCase()) ||
    item.tags?.some(t => t.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const handleSelectItem = useCallback(async (item: TechItemView, role: TechChoiceRole) => {
    try {
      await setTechChoice.mutateAsync({
        dimensionSlug: dimension.slug,
        itemSlug: item.slug,
        role,
      });
    } catch (error) {
      console.error('Failed to set tech choice:', error);
    }
  }, [setTechChoice, dimension.slug]);

  const handleRemoveItem = useCallback(async (item: TechItemView) => {
    try {
      await removeTechChoice.mutateAsync({
        dimensionSlug: dimension.slug,
        itemSlug: item.slug,
      });
    } catch (error) {
      console.error('Failed to remove tech choice:', error);
    }
  }, [removeTechChoice, dimension.slug]);

  const selectedCount = dimension.choices.length;

  return (
    <AccordionItem value={dimension.slug} className="border rounded-lg">
      <AccordionTrigger className="px-4 hover:no-underline">
        <div className="flex items-center gap-3">
          <span className="font-medium">{dimension.name}</span>
          {selectedCount > 0 && (
            <Badge variant="secondary" className="ml-2">
              {selectedCount} selected
            </Badge>
          )}
        </div>
      </AccordionTrigger>
      <AccordionContent className="px-4 pb-4">
        {dimension.description && (
          <p className="text-sm text-muted-foreground mb-4">
            {dimension.description}
          </p>
        )}

        {/* Selected items */}
        {dimension.choices.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-4">
            {dimension.choices.map((choice) => (
              <SelectedChip
                key={choice.id}
                choice={choice}
                onRemove={() => {
                  if (choice.tech_item_slug) {
                    handleRemoveItem({ slug: choice.tech_item_slug } as TechItemView);
                  }
                }}
              />
            ))}
          </div>
        )}

        {/* Role selector - inline buttons */}
        <div className="flex items-center gap-2 flex-wrap mb-4">
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

        {/* Available items */}
        <div className="flex flex-wrap gap-2">
          {filteredItems
            .filter(item => !choiceMap.has(item.slug))
            .map((item) => (
              <ItemChip
                key={item.slug}
                item={item}
                onSelect={() => handleSelectItem(item, selectedRole)}
              />
            ))}
        </div>

        {filteredItems.length === 0 && searchQuery && (
          <p className="text-sm text-muted-foreground">
            No items match &quot;{searchQuery}&quot;
          </p>
        )}
      </AccordionContent>
    </AccordionItem>
  );
}

function ItemChip({ 
  item, 
  onSelect 
}: { 
  item: TechItemView;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        'px-3 py-1.5 text-sm rounded-full border transition-colors',
        'bg-muted/50 hover:bg-muted border-transparent hover:border-primary/50'
      )}
    >
      {item.name}
    </button>
  );
}

function SelectedChip({ 
  choice, 
  onRemove 
}: { 
  choice: TechChoiceView;
  onRemove: () => void;
}) {
  const roleOption = roleOptions.find(r => r.value === choice.role);
  const RoleIcon = roleOption?.icon || Target;
  
  const roleColors: Record<TechChoiceRole, string> = {
    [TechChoiceRole.TARGET]: 'bg-green-100 text-green-800 border-green-300',
    [TechChoiceRole.LEGACY]: 'bg-amber-100 text-amber-800 border-amber-300',
    [TechChoiceRole.OPTIONAL]: 'bg-blue-100 text-blue-800 border-blue-300',
    [TechChoiceRole.MUST_AVOID]: 'bg-red-100 text-red-800 border-red-300',
    [TechChoiceRole.TBD]: 'bg-gray-100 text-gray-800 border-gray-300',
  };

  return (
    <div className={cn(
      "flex items-center gap-1 px-2 py-1 text-sm rounded-full border",
      roleColors[choice.role as TechChoiceRole] || roleColors[TechChoiceRole.TARGET]
    )}>
      <RoleIcon className="h-3 w-3" />
      <span className="font-medium">{choice.tech_item_name}</span>
      <button
        onClick={onRemove}
        className="ml-1 rounded-full p-0.5 hover:bg-black/10"
      >
        <X className="h-3 w-3" />
      </button>
    </div>
  );
}
