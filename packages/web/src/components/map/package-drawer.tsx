'use client';

import { X, Package, Clock, CheckCircle2, AlertCircle, Waves, ExternalLink, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { PackageNodeData, PackageStatus } from './package-node';
import { GenerationDialog } from '@/components/generation/generation-dialog';
import Link from 'next/link';

interface PackageDrawerProps {
  packageId: string;
  data: PackageNodeData;
  projectSlug: string;
  onClose: () => void;
  onWaveChange?: (wave: number) => void;
}

const statusConfig: Record<PackageStatus, { label: string; icon: React.ElementType; color: string }> = {
  pending: { label: 'Pending', icon: Clock, color: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200' },
  analyzing: { label: 'Analyzing', icon: Clock, color: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' },
  analyzed: { label: 'Analyzed', icon: CheckCircle2, color: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' },
  failed: { label: 'Failed', icon: AlertCircle, color: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200' },
};

export function PackageDrawer({ packageId, data, projectSlug, onClose, onWaveChange }: PackageDrawerProps) {
  const statusInfo = statusConfig[data.status];
  const StatusIcon = statusInfo.icon;
  const blockerCount = data.blockers || 0;
  const autoResolved = data.autoResolved || 0;
  const pendingBlockers = blockerCount - autoResolved;

  return (
    <div className="fixed inset-y-0 right-0 w-96 bg-background border-l shadow-xl z-50 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b">
        <div className="flex items-center gap-2">
          <Package className="h-5 w-5 text-muted-foreground" />
          <h2 className="font-semibold truncate">{data.label}</h2>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4 space-y-6">
        {/* Status */}
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-muted-foreground">Status</h3>
          <div className="flex items-center gap-2">
            <Badge className={cn(statusInfo.color, 'gap-1')}>
              <StatusIcon className="h-3 w-3" />
              {statusInfo.label}
            </Badge>
          </div>
        </div>

        <Separator />

        {/* Wave Assignment */}
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-muted-foreground">Migration Wave</h3>
          <div className="flex items-center gap-2">
            <Waves className="h-4 w-4 text-muted-foreground" />
            {data.wave !== undefined ? (
              <span className="font-mono font-medium">Wave {data.wave}</span>
            ) : (
              <span className="text-muted-foreground italic">Not assigned</span>
            )}
          </div>
          {onWaveChange && (
            <div className="flex gap-1 mt-2">
              {[1, 2, 3, 4, 5].map((w) => (
                <Button
                  key={w}
                  variant={data.wave === w ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => onWaveChange(w)}
                  className="w-10"
                >
                  {w}
                </Button>
              ))}
            </div>
          )}
        </div>

        <Separator />

        {/* Blockers */}
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-muted-foreground">Blockers</h3>
          <div className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span>Total Blockers</span>
              <span className="font-mono">{blockerCount}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span>Auto-Resolved</span>
              <span className="font-mono text-green-600">{autoResolved}</span>
            </div>
            <div className="flex items-center justify-between text-sm font-medium">
              <span>Pending Review</span>
              <span className={cn('font-mono', pendingBlockers > 0 ? 'text-amber-600' : 'text-green-600')}>
                {pendingBlockers}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="p-4 border-t space-y-2">
        <GenerationDialog
          projectSlug={projectSlug}
          packageId={packageId}
          packageName={data.label}
          trigger={
            <Button variant="default" className="w-full gap-2">
              <Sparkles className="h-4 w-4" />
              Generate Notebooks
            </Button>
          }
        />
        <Button asChild variant="outline" className="w-full gap-2">
          <Link href={`/projects/${projectSlug}/packages/${packageId}` as any}>
            View Package Details
            <ExternalLink className="h-4 w-4" />
          </Link>
        </Button>
      </div>
    </div>
  );
}
