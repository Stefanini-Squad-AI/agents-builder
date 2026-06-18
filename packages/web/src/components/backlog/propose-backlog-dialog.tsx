'use client';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Loader2, Sparkles, AlertTriangle } from 'lucide-react';

interface ProposeBacklogDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  isPending: boolean;
  hasExistingBacklog: boolean;
}

export function ProposeBacklogDialog({
  open,
  onOpenChange,
  onConfirm,
  isPending,
  hasExistingBacklog,
}: ProposeBacklogDialogProps) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            Propose Backlog
          </AlertDialogTitle>
          <AlertDialogDescription className="space-y-3">
            {hasExistingBacklog ? (
              <>
                <div className="flex items-start gap-2 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
                  <AlertTriangle className="h-5 w-5 text-yellow-600 dark:text-yellow-400 flex-shrink-0 mt-0.5" />
                  <div className="text-yellow-800 dark:text-yellow-200 text-sm">
                    <p className="font-medium">Warning: Existing backlog detected</p>
                    <p className="mt-1">
                      This will create <strong>additional</strong> phases and cards.
                      Existing phases and cards will not be modified.
                    </p>
                  </div>
                </div>
                <p>
                  The AI will analyze your project context and skills to propose
                  a new set of phases and cards.
                </p>
              </>
            ) : (
              <p>
                The AI will analyze your project context, Q&A answers, tech choices,
                and skills to generate a structured backlog with phases and cards.
              </p>
            )}
            <p className="text-sm text-muted-foreground">
              This may take 30-60 seconds depending on project complexity.
            </p>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isPending}>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm} disabled={isPending}>
            {isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Proposing...
              </>
            ) : (
              <>
                <Sparkles className="mr-2 h-4 w-4" />
                Propose
              </>
            )}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export default ProposeBacklogDialog;
