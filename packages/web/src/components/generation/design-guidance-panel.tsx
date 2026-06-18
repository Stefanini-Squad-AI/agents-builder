'use client';

import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Loader2,
  Zap,
  AlertTriangle,
  Info,
  Database,
  RefreshCw,
  Layers,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useDesignGuidance } from '@/lib/api/queries/use-generation';
import type {
  DataPattern,
  MedallionLayer,
  TaskPatternResult,
} from '@/lib/api/types';

interface DesignGuidancePanelProps {
  projectSlug: string;
  packageId: string;
}

// Pattern display names
const patternLabels: Record<DataPattern, string> = {
  merge: 'MERGE (Upsert)',
  delete_insert: 'DELETE + INSERT',
  append_only: 'APPEND Only',
  update_in_place: 'UPDATE In-Place',
  scd_type_1: 'SCD Type 1',
  scd_type_2: 'SCD Type 2',
  scd_type_3: 'SCD Type 3',
  soft_delete: 'Soft Delete',
  hard_delete: 'Hard Delete',
  watermark: 'Watermark',
  cdc: 'CDC',
  delta_diff: 'Delta Diff',
  lookup_enrich: 'Lookup/Enrich',
  aggregate: 'Aggregate',
  pivot_unpivot: 'Pivot/Unpivot',
  unknown: 'Unknown',
};

// Layer display info
const layerConfig: Record<MedallionLayer, { label: string; color: string }> = {
  bronze: { label: 'Bronze', color: 'bg-amber-600 text-white' },
  silver: { label: 'Silver', color: 'bg-slate-400 text-white' },
  gold: { label: 'Gold', color: 'bg-yellow-500 text-black' },
  'n/a': { label: 'N/A', color: 'bg-muted text-muted-foreground' },
};

// Pattern category icons
function PatternIcon({ pattern }: { pattern: DataPattern }) {
  const iconClass = 'h-4 w-4';
  
  switch (pattern) {
    case 'merge':
    case 'scd_type_1':
    case 'scd_type_2':
    case 'scd_type_3':
      return <RefreshCw className={cn(iconClass, 'text-blue-500')} />;
    case 'append_only':
    case 'cdc':
    case 'watermark':
      return <Database className={cn(iconClass, 'text-green-500')} />;
    case 'aggregate':
    case 'lookup_enrich':
      return <Layers className={cn(iconClass, 'text-purple-500')} />;
    default:
      return <Database className={cn(iconClass, 'text-muted-foreground')} />;
  }
}

export function DesignGuidancePanel({
  projectSlug,
  packageId,
}: DesignGuidancePanelProps) {
  const { data: analysis, isLoading, error } = useDesignGuidance(
    projectSlug,
    packageId
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !analysis) {
    return (
      <div className="flex items-center justify-center h-32 text-muted-foreground">
        <AlertTriangle className="h-4 w-4 mr-2" />
        Failed to load design analysis
      </div>
    );
  }

  const taskCount = analysis.task_patterns.length;
  const unknownCount = analysis.pattern_summary['unknown'] || 0;
  const recognizedPct = taskCount > 0 
    ? Math.round(((taskCount - unknownCount) / taskCount) * 100) 
    : 0;

  return (
    <div className="space-y-4">
      {/* Summary Row */}
      <div className="flex items-center gap-4 text-sm">
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">Tasks analyzed:</span>
          <Badge variant="secondary">{taskCount}</Badge>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">Patterns recognized:</span>
          <Badge variant={recognizedPct >= 80 ? 'default' : 'outline'}>
            {recognizedPct}%
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          {analysis.photon_eligible ? (
            <>
              <Zap className="h-4 w-4 text-yellow-500" />
              <span className="text-sm text-green-600">Photon eligible</span>
            </>
          ) : (
            <>
              <AlertTriangle className="h-4 w-4 text-orange-500" />
              <span className="text-sm text-orange-600">Photon limited</span>
            </>
          )}
        </div>
      </div>

      {/* Performance Notes */}
      {analysis.performance_notes.length > 0 && (
        <div className="rounded-md border border-blue-200 bg-blue-50 p-3 text-sm">
          <div className="flex items-center gap-2 font-medium text-blue-800 mb-1">
            <Info className="h-4 w-4" />
            Performance Recommendations
          </div>
          <ul className="list-disc list-inside text-blue-700 space-y-1">
            {analysis.performance_notes.map((note, idx) => (
              <li key={idx}>{note}</li>
            ))}
          </ul>
        </div>
      )}

      <Separator />

      {/* Layer Summary */}
      <div className="space-y-2">
        <Label>Medallion Layer Distribution</Label>
        <div className="flex gap-3">
          {Object.entries(analysis.layer_summary).map(([layer, count]) => {
            const config = layerConfig[layer as MedallionLayer];
            return (
              <div key={layer} className="flex items-center gap-2">
                <Badge className={cn('text-xs', config?.color || '')}>
                  {config?.label || layer}
                </Badge>
                <span className="text-sm text-muted-foreground">{count}</span>
              </div>
            );
          })}
        </div>
      </div>

      <Separator />

      {/* Task Pattern Table */}
      <div className="space-y-2">
        <Label>Per-Task Analysis</Label>
        <ScrollArea className="h-[200px] rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[200px]">Task</TableHead>
                <TableHead>Pattern</TableHead>
                <TableHead>Layer</TableHead>
                <TableHead className="w-[150px]">Target Table</TableHead>
                <TableHead className="text-right">Confidence</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {analysis.task_patterns.map((tp, idx) => (
                <TaskPatternRow key={idx} result={tp} />
              ))}
            </TableBody>
          </Table>
        </ScrollArea>
      </div>
    </div>
  );
}

function TaskPatternRow({ result }: { result: TaskPatternResult }) {
  const layerCfg = layerConfig[result.layer];
  const confidencePct = Math.round(result.confidence * 100);

  return (
    <TableRow>
      <TableCell className="font-medium truncate max-w-[200px]" title={result.task_name}>
        {result.task_name}
      </TableCell>
      <TableCell>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="flex items-center gap-2 cursor-help">
                <PatternIcon pattern={result.pattern} />
                <span>{patternLabels[result.pattern] || result.pattern_name}</span>
              </div>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs">
              <div className="space-y-1">
                <p className="font-medium">{result.pattern_name}</p>
                {result.detection_evidence.length > 0 && (
                  <ul className="text-xs list-disc list-inside">
                    {result.detection_evidence.map((e, i) => (
                      <li key={i}>{e}</li>
                    ))}
                  </ul>
                )}
              </div>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </TableCell>
      <TableCell>
        <Badge className={cn('text-xs', layerCfg?.color || '')}>
          {layerCfg?.label || result.layer}
        </Badge>
      </TableCell>
      <TableCell className="font-mono text-xs truncate max-w-[150px]" title={result.target_table || ''}>
        {result.target_table || '—'}
      </TableCell>
      <TableCell className="text-right">
        <span
          className={cn(
            'text-sm',
            confidencePct >= 70 ? 'text-green-600' : confidencePct >= 40 ? 'text-yellow-600' : 'text-red-500'
          )}
        >
          {confidencePct}%
        </span>
      </TableCell>
    </TableRow>
  );
}
