'use client';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { GapStatus, GapsStatsResponse } from '@/lib/api/types';
import { cn } from '@/lib/utils';

type FilterValue = GapStatus | 'all';

interface GapFilterChipsProps {
  value: FilterValue;
  onChange: (next: FilterValue) => void;
  stats: GapsStatsResponse | undefined;
}

const FILTERS: { value: FilterValue; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'open', label: 'Open' },
  { value: 'addressed_by_skill', label: 'By skill' },
  { value: 'covered_by_mcp', label: 'By MCP' },
  { value: 'out_of_scope', label: 'Out of scope' },
];

function countFor(filter: FilterValue, stats?: GapsStatsResponse): number | undefined {
  if (!stats) return undefined;
  if (filter === 'all') return stats.total;
  return stats[filter];
}

export function GapFilterChips({ value, onChange, stats }: GapFilterChipsProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {FILTERS.map((filter) => {
        const isActive = filter.value === value;
        const count = countFor(filter.value, stats);
        return (
          <Button
            key={filter.value}
            variant={isActive ? 'default' : 'outline'}
            size="sm"
            onClick={() => onChange(filter.value)}
            className="h-8"
          >
            {filter.label}
            {count !== undefined && (
              <Badge
                variant="secondary"
                className={cn(
                  'ml-2 h-5 px-1.5 text-xs',
                  isActive && 'bg-primary-foreground/20 text-primary-foreground'
                )}
              >
                {count}
              </Badge>
            )}
          </Button>
        );
      })}
    </div>
  );
}

export type { FilterValue as GapFilterValue };
