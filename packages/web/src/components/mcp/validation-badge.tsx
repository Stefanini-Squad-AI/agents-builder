'use client';

import { Badge } from '@/components/ui/badge';
import { CheckCircle2, AlertCircle, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ValidationBadgeProps {
  validatedAt: string | null;
  hasError: boolean;
  className?: string;
}

export function ValidationBadge({
  validatedAt,
  hasError,
  className,
}: ValidationBadgeProps) {
  if (hasError) {
    return (
      <Badge
        variant="outline"
        className={cn(
          'border-destructive/40 bg-destructive/10 text-destructive',
          className
        )}
      >
        <AlertCircle className="mr-1 h-3 w-3" />
        Invalid
      </Badge>
    );
  }

  if (!validatedAt) {
    return (
      <Badge variant="outline" className={cn('text-muted-foreground', className)}>
        <Clock className="mr-1 h-3 w-3" />
        Not validated
      </Badge>
    );
  }

  return (
    <Badge
      variant="outline"
      className={cn(
        'border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
        className
      )}
    >
      <CheckCircle2 className="mr-1 h-3 w-3" />
      Validated
    </Badge>
  );
}
