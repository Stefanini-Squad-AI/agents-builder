'use client';

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { DagNodeView, CardType, CardStatus } from '@/lib/api/types';
import { FileText, Lightbulb, Wrench, Presentation, ExternalLink, Circle, Bug } from 'lucide-react';

// Card type icons and labels
const typeConfig: Record<CardType, { icon: React.ElementType; label: string }> = {
  [CardType.STORY]: { icon: FileText, label: 'Story' },
  [CardType.TASK]: { icon: Wrench, label: 'Task' },
  [CardType.BUG]: { icon: Bug, label: 'Bug' },
  [CardType.SPIKE]: { icon: Lightbulb, label: 'Spike' },
  [CardType.DEMO]: { icon: Presentation, label: 'Demo' },
};

// Status colors
const statusConfig: Record<CardStatus, { color: string; label: string }> = {
  [CardStatus.DRAFT]: { color: 'secondary', label: 'Draft' },
  [CardStatus.READY]: { color: 'default', label: 'Ready' },
  [CardStatus.IN_PROGRESS]: { color: 'default', label: 'In Progress' },
  [CardStatus.DONE]: { color: 'default', label: 'Done' },
};

interface CardDrawerProps {
  node: DagNodeView | null;
  open: boolean;
  onClose: () => void;
  onEdit: () => void;
}

export function CardDrawer({ node, open, onClose, onEdit }: CardDrawerProps) {
  if (!node) return null;

  const { icon: TypeIcon, label: typeLabel } = typeConfig[node.type] || typeConfig[CardType.TASK];
  const { label: statusLabel } = statusConfig[node.status] || statusConfig[CardStatus.DRAFT];

  return (
    <Sheet open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <SheetContent side="right" className="w-[400px] sm:w-[450px]">
        <SheetHeader>
          <div className="flex items-center gap-2 text-muted-foreground">
            <TypeIcon className="h-4 w-4" />
            <span className="font-mono text-sm">{node.code}</span>
          </div>
          <SheetTitle className="text-xl">{node.title}</SheetTitle>
          <SheetDescription>
            Card details and quick actions
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          {/* Status and Type */}
          <div className="flex items-center gap-3 flex-wrap">
            <Badge variant="outline" className="gap-1">
              <TypeIcon className="h-3 w-3" />
              {typeLabel}
            </Badge>
            <Badge variant="secondary">{statusLabel}</Badge>
            {node.story_points && (
              <Badge variant="outline" className="gap-1">
                <Circle className="h-3 w-3 fill-current" />
                {node.story_points} pts
              </Badge>
            )}
          </div>

          <Separator />

          {/* Phase Info */}
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-muted-foreground">Phase</h4>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm">{node.phase_code}</span>
              <span className="text-muted-foreground">·</span>
              <span>{node.phase_name}</span>
            </div>
          </div>

          <Separator />

          {/* Quick Stats */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <h4 className="text-sm font-medium text-muted-foreground">Card ID</h4>
              <p className="font-mono text-xs text-muted-foreground truncate">{node.id}</p>
            </div>
            <div className="space-y-1">
              <h4 className="text-sm font-medium text-muted-foreground">Status</h4>
              <p>{statusLabel}</p>
            </div>
          </div>

          <Separator />

          {/* Actions */}
          <div className="flex flex-col gap-2">
            <Button onClick={onEdit} className="w-full">
              <ExternalLink className="mr-2 h-4 w-4" />
              Open Card Editor
            </Button>
            <Button variant="outline" onClick={onClose} className="w-full">
              Close
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
