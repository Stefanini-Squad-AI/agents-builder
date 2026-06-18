'use client';

import { MapStats } from '@/lib/api/types';
import { cn } from '@/lib/utils';
import { 
  Package, 
  Database, 
  GitBranch, 
  Layers, 
  AlertTriangle, 
  Waves,
  HelpCircle 
} from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface MapStatsPanelProps {
  stats: MapStats;
  className?: string;
}

interface StatItemProps {
  icon: React.ReactNode;
  label: string;
  value: number;
  tooltip?: string;
  variant?: 'default' | 'warning' | 'success';
}

function StatItem({ icon, label, value, tooltip, variant = 'default' }: StatItemProps) {
  const valueColor = {
    default: 'text-foreground',
    warning: 'text-amber-600 dark:text-amber-400',
    success: 'text-green-600 dark:text-green-400',
  };

  const content = (
    <div className="flex items-center gap-2 px-3 py-2">
      <div className="text-muted-foreground">{icon}</div>
      <div className="flex flex-col">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className={cn('text-lg font-semibold tabular-nums', valueColor[variant])}>
          {value}
        </span>
      </div>
    </div>
  );

  if (tooltip) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="cursor-help">{content}</div>
          </TooltipTrigger>
          <TooltipContent>
            <p>{tooltip}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return content;
}

export function MapStatsPanel({ stats, className }: MapStatsPanelProps) {
  const analysisProgress = stats.total_packages > 0 
    ? Math.round((stats.analyzed_packages / stats.total_packages) * 100)
    : 0;

  return (
    <div className={cn('bg-card border rounded-lg shadow-sm', className)}>
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 divide-x">
        <StatItem
          icon={<Package className="h-4 w-4" />}
          label="Packages"
          value={stats.total_packages}
          tooltip={`${stats.analyzed_packages} analyzed (${analysisProgress}%)`}
          variant={analysisProgress < 100 ? 'default' : 'success'}
        />
        <StatItem
          icon={<Database className="h-4 w-4" />}
          label="Objects"
          value={stats.total_objects}
          tooltip="Tables, files, APIs discovered across all packages"
        />
        <StatItem
          icon={<GitBranch className="h-4 w-4" />}
          label="Dependencies"
          value={stats.total_dependencies}
          tooltip="Data flow connections between packages"
        />
        <StatItem
          icon={<Layers className="h-4 w-4" />}
          label="Clusters"
          value={stats.cluster_count}
          tooltip="Groups of related packages"
        />
        <StatItem
          icon={<HelpCircle className="h-4 w-4" />}
          label="Orphans"
          value={stats.orphan_count}
          tooltip="Packages with no detected dependencies"
          variant={stats.orphan_count > 0 ? 'warning' : 'default'}
        />
        <StatItem
          icon={<AlertTriangle className="h-4 w-4" />}
          label="Cycles"
          value={stats.cycles_detected}
          tooltip="Circular dependencies detected"
          variant={stats.cycles_detected > 0 ? 'warning' : 'default'}
        />
        <StatItem
          icon={<Waves className="h-4 w-4" />}
          label="Waves"
          value={stats.suggested_waves}
          tooltip="Suggested migration waves"
        />
      </div>
    </div>
  );
}
