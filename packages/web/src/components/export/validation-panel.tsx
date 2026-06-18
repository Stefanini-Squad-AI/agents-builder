'use client';

import { ValidationIssueView } from '@/lib/api/types';
import { cn } from '@/lib/utils';
import { AlertCircle, AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';

interface ValidationPanelProps {
  issues: ValidationIssueView[];
  isLoading?: boolean;
}

export function ValidationPanel({ issues, isLoading }: ValidationPanelProps) {
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-8 gap-2">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">Running validation checks...</p>
      </div>
    );
  }

  if (!issues || issues.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 gap-2 text-green-600">
        <CheckCircle2 className="h-8 w-8" />
        <p className="text-sm font-medium">All validation checks passed</p>
        <p className="text-xs text-muted-foreground">Your project is ready to export</p>
      </div>
    );
  }

  // Group issues by severity
  const errors = issues.filter((i) => i.severity === 'error');
  const warnings = issues.filter((i) => i.severity === 'warning');

  return (
    <ScrollArea className="h-[300px]">
      <div className="space-y-4">
        {/* Errors */}
        {errors.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium flex items-center gap-2 text-red-600">
              <AlertCircle className="h-4 w-4" />
              Errors ({errors.length})
            </h4>
            <div className="space-y-2">
              {errors.map((issue, index) => (
                <IssueItem key={`error-${index}`} issue={issue} />
              ))}
            </div>
          </div>
        )}

        {/* Warnings */}
        {warnings.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium flex items-center gap-2 text-yellow-600">
              <AlertTriangle className="h-4 w-4" />
              Warnings ({warnings.length})
            </h4>
            <div className="space-y-2">
              {warnings.map((issue, index) => (
                <IssueItem key={`warning-${index}`} issue={issue} />
              ))}
            </div>
          </div>
        )}
      </div>
    </ScrollArea>
  );
}

interface IssueItemProps {
  issue: ValidationIssueView;
}

function IssueItem({ issue }: IssueItemProps) {
  const isError = issue.severity === 'error';

  return (
    <div
      className={cn(
        'p-3 rounded-lg border text-sm',
        isError
          ? 'bg-red-50 border-red-200 dark:bg-red-950/50 dark:border-red-800'
          : 'bg-yellow-50 border-yellow-200 dark:bg-yellow-950/50 dark:border-yellow-800'
      )}
    >
      <div className="flex items-start gap-2">
        {isError ? (
          <AlertCircle className="h-4 w-4 text-red-500 mt-0.5 shrink-0" />
        ) : (
          <AlertTriangle className="h-4 w-4 text-yellow-500 mt-0.5 shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <p className={cn('font-medium', isError ? 'text-red-700 dark:text-red-300' : 'text-yellow-700 dark:text-yellow-300')}>
            {issue.message}
          </p>
          <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
            <code className="px-1 py-0.5 bg-muted rounded">{issue.code}</code>
            {issue.location && Object.entries(issue.location).map(([key, value]) => (
              <span key={key}>
                {key}: <code className="px-1 py-0.5 bg-muted rounded">{value}</code>
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
