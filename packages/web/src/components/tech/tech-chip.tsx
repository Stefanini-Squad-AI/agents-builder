'use client';

import { forwardRef } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { 
  Check, 
  X, 
  Target, 
  Clock, 
  CircleDot, 
  Ban, 
  HelpCircle,
  Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { TechChoiceRole, TechChoiceSource } from '@/lib/api/types';

interface TechChipProps {
  itemSlug: string;
  itemName: string;
  isSelected: boolean;
  role?: TechChoiceRole;
  source?: TechChoiceSource;
  accepted?: boolean;
  confidence?: number;
  isCustom?: boolean;
  onSelect?: () => void;
  onDeselect?: () => void;
  onAccept?: () => void;
  onDismiss?: () => void;
  disabled?: boolean;
  className?: string;
}

const roleIcons: Record<TechChoiceRole, typeof Target> = {
  [TechChoiceRole.TARGET]: Target,
  [TechChoiceRole.LEGACY]: Clock,
  [TechChoiceRole.OPTIONAL]: CircleDot,
  [TechChoiceRole.MUST_AVOID]: Ban,
  [TechChoiceRole.TBD]: HelpCircle,
};

const roleColors: Record<TechChoiceRole, string> = {
  [TechChoiceRole.TARGET]: 'bg-green-100 text-green-800 border-green-300 dark:bg-green-900 dark:text-green-100 dark:border-green-700',
  [TechChoiceRole.LEGACY]: 'bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-900 dark:text-amber-100 dark:border-amber-700',
  [TechChoiceRole.OPTIONAL]: 'bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-900 dark:text-blue-100 dark:border-blue-700',
  [TechChoiceRole.MUST_AVOID]: 'bg-red-100 text-red-800 border-red-300 dark:bg-red-900 dark:text-red-100 dark:border-red-700',
  [TechChoiceRole.TBD]: 'bg-gray-100 text-gray-800 border-gray-300 dark:bg-gray-800 dark:text-gray-100 dark:border-gray-600',
};

/**
 * Tech chip component for displaying and selecting tech items.
 * Shows different states: unselected, selected (with role), LLM suggested (pending).
 */
export const TechChip = forwardRef<HTMLButtonElement, TechChipProps>(({
  itemSlug,
  itemName,
  isSelected,
  role,
  source,
  accepted,
  confidence,
  isCustom,
  onSelect,
  onDeselect,
  onAccept,
  onDismiss,
  disabled,
  className,
}, ref) => {
  const isLlmSuggestion = source === TechChoiceSource.LLM_SUGGESTED && !accepted;
  const RoleIcon = role ? roleIcons[role] : null;

  // LLM suggestion state - show accept/dismiss buttons
  if (isLlmSuggestion) {
    return (
      <div
        className={cn(
          'inline-flex items-center gap-1 px-2 py-1 rounded-full border-2 border-dashed',
          'border-purple-400 bg-purple-50 dark:bg-purple-950 dark:border-purple-600',
          className
        )}
      >
        <Sparkles className="h-3 w-3 text-purple-500" />
        <span className="text-sm font-medium text-purple-700 dark:text-purple-300">
          {itemName}
        </span>
        {confidence !== undefined && (
          <Badge variant="secondary" className="text-xs px-1 py-0 h-4">
            {Math.round(confidence * 100)}%
          </Badge>
        )}
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-5 w-5 rounded-full hover:bg-green-100 dark:hover:bg-green-900"
          onClick={onAccept}
          disabled={disabled}
        >
          <Check className="h-3 w-3 text-green-600" />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-5 w-5 rounded-full hover:bg-red-100 dark:hover:bg-red-900"
          onClick={onDismiss}
          disabled={disabled}
        >
          <X className="h-3 w-3 text-red-600" />
        </Button>
      </div>
    );
  }

  // Selected state
  if (isSelected && role) {
    return (
      <button
        ref={ref}
        type="button"
        onClick={onDeselect}
        disabled={disabled}
        className={cn(
          'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border transition-all',
          'hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          'disabled:opacity-50 disabled:pointer-events-none',
          roleColors[role],
          className
        )}
      >
        {RoleIcon && <RoleIcon className="h-3.5 w-3.5" />}
        <span className="text-sm font-medium">{itemName}</span>
        {isCustom && (
          <Badge variant="outline" className="text-xs px-1 py-0 h-4 ml-1">
            custom
          </Badge>
        )}
        <X className="h-3.5 w-3.5 ml-1 opacity-60" />
      </button>
    );
  }

  // Unselected state
  return (
    <button
      ref={ref}
      type="button"
      onClick={onSelect}
      disabled={disabled}
      className={cn(
        'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border transition-all',
        'border-border bg-background hover:bg-accent hover:border-accent-foreground/20',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        'disabled:opacity-50 disabled:pointer-events-none',
        className
      )}
    >
      <span className="text-sm text-muted-foreground">{itemName}</span>
      {isCustom && (
        <Badge variant="outline" className="text-xs px-1 py-0 h-4">
          custom
        </Badge>
      )}
    </button>
  );
});

TechChip.displayName = 'TechChip';

export default TechChip;
