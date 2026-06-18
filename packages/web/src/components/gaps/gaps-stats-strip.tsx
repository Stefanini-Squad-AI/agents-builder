'use client';

import { Card, CardContent } from '@/components/ui/card';
import { GapsStatsResponse } from '@/lib/api/types';
import {
  AlertOctagon,
  Sparkles,
  Plug,
  CircleSlash,
  ListChecks,
} from 'lucide-react';

interface GapsStatsStripProps {
  stats: GapsStatsResponse | undefined;
  isLoading?: boolean;
}

export function GapsStatsStrip({ stats, isLoading }: GapsStatsStripProps) {
  const items = [
    {
      label: 'Total',
      value: stats?.total ?? 0,
      icon: ListChecks,
      tone: 'text-foreground',
    },
    {
      label: 'Open',
      value: stats?.open ?? 0,
      icon: AlertOctagon,
      tone: 'text-amber-600 dark:text-amber-400',
    },
    {
      label: 'By skill',
      value: stats?.addressed_by_skill ?? 0,
      icon: Sparkles,
      tone: 'text-emerald-600 dark:text-emerald-400',
    },
    {
      label: 'By MCP',
      value: stats?.covered_by_mcp ?? 0,
      icon: Plug,
      tone: 'text-sky-600 dark:text-sky-400',
    },
    {
      label: 'Out of scope',
      value: stats?.out_of_scope ?? 0,
      icon: CircleSlash,
      tone: 'text-muted-foreground',
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {items.map(({ label, value, icon: Icon, tone }) => (
        <Card key={label}>
          <CardContent className="flex items-center gap-3 p-4">
            <Icon className={`h-5 w-5 ${tone}`} />
            <div className="flex flex-col">
              <span className="text-xs text-muted-foreground">{label}</span>
              <span className="text-2xl font-semibold leading-tight">
                {isLoading ? '—' : value}
              </span>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
