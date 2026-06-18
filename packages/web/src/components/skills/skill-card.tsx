'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
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
import {
  BookOpen,
  Code2,
  Search,
  ListChecks,
  MoreVertical,
  Pencil,
  Trash2,
  FileText,
  FolderOpen,
  Loader2,
  CheckCircle2,
  Clock,
  AlertTriangle,
  ExternalLink,
} from 'lucide-react';
import { useState } from 'react';
import { SkillView, SkillKind, SkillDraftStatus } from '@/lib/api/types';
import { cn } from '@/lib/utils';
import Link from 'next/link';

interface SkillCardProps {
  skill: SkillView;
  projectSlug?: string;
  onEdit?: (skill: SkillView) => void;
  onDelete?: (skill: SkillView) => void;
  onClick?: (skill: SkillView) => void;
  isDeleting?: boolean;
}

/**
 * Get icon for skill kind
 */
function getKindIcon(kind: SkillKind) {
  switch (kind) {
    case SkillKind.CONTEXT:
      return BookOpen;
    case SkillKind.ANALYZER:
      return Search;
    case SkillKind.AUTHORING:
      return Code2;
    case SkillKind.PROCEDURE:
      return ListChecks;
    default:
      return FileText;
  }
}

/**
 * Get color for skill kind badge
 */
function getKindColor(kind: SkillKind): string {
  switch (kind) {
    case SkillKind.CONTEXT:
      return 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300';
    case SkillKind.ANALYZER:
      return 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300';
    case SkillKind.AUTHORING:
      return 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300';
    case SkillKind.PROCEDURE:
      return 'bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300';
    default:
      return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300';
  }
}

/**
 * Get display info for draft status
 */
function getDraftStatusDisplay(status: SkillDraftStatus | undefined) {
  switch (status) {
    case 'pending':
      return {
        icon: Clock,
        label: 'Queued',
        className: 'text-blue-600 dark:text-blue-400',
      };
    case 'drafting':
      return {
        icon: Loader2,
        label: 'Drafting...',
        className: 'text-blue-600 dark:text-blue-400',
        animate: true,
      };
    case 'success':
      return {
        icon: CheckCircle2,
        label: 'Drafted',
        className: 'text-green-600 dark:text-green-400',
      };
    case 'error':
      return {
        icon: AlertTriangle,
        label: 'Error',
        className: 'text-red-600 dark:text-red-400',
      };
    default:
      return null;
  }
}

/**
 * Card component for displaying a skill in a grid
 */
export function SkillCard({
  skill,
  projectSlug,
  onEdit,
  onDelete,
  onClick,
  isDeleting = false,
}: SkillCardProps) {
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const KindIcon = getKindIcon(skill.kind);
  const hasContent = skill.body_md && skill.body_md.trim().length > 0;
  const resourceCount = skill.resources?.length || 0;
  const draftStatusDisplay = getDraftStatusDisplay(skill.draft_status);

  const handleClick = () => {
    if (onClick) {
      onClick(skill);
    }
  };

  const handleDelete = () => {
    setShowDeleteDialog(false);
    if (onDelete) {
      onDelete(skill);
    }
  };

  return (
    <>
      <Card
        className={cn(
          'group relative cursor-pointer transition-all hover:shadow-md hover:border-primary/50',
          isDeleting && 'opacity-50 pointer-events-none'
        )}
        onClick={handleClick}
      >
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-start gap-3 min-w-0">
              <div
                className={cn(
                  'p-2 rounded-lg shrink-0',
                  getKindColor(skill.kind)
                )}
              >
                <KindIcon className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <CardTitle className="text-base truncate">{skill.name}</CardTitle>
                <Badge
                  variant="secondary"
                  className={cn('mt-1 text-xs capitalize', getKindColor(skill.kind))}
                >
                  {skill.kind}
                </Badge>
              </div>
            </div>

            {/* Actions menu */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <MoreVertical className="h-4 w-4" />
                  <span className="sr-only">Actions</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {onEdit && (
                  <DropdownMenuItem
                    onClick={(e) => {
                      e.stopPropagation();
                      onEdit(skill);
                    }}
                  >
                    <Pencil className="mr-2 h-4 w-4" />
                    Edit
                  </DropdownMenuItem>
                )}
                {onDelete && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onClick={(e) => {
                        e.stopPropagation();
                        setShowDeleteDialog(true);
                      }}
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Delete
                    </DropdownMenuItem>
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </CardHeader>

        <CardContent>
          <CardDescription className="line-clamp-2 text-sm">
            {skill.description}
          </CardDescription>

          {/* Metadata row */}
          <div className="flex items-center gap-3 mt-3 text-xs text-muted-foreground flex-wrap">
            {/* Draft status indicator */}
            {draftStatusDisplay && (
              <span className={cn('flex items-center gap-1', draftStatusDisplay.className)}>
                <draftStatusDisplay.icon
                  className={cn('h-3 w-3', draftStatusDisplay.animate && 'animate-spin')}
                />
                {draftStatusDisplay.label}
                {skill.draft_status === 'error' && skill.last_llm_run_id && projectSlug && (
                  <Link
                    href={`/projects/${projectSlug}/llm-runs`}
                    onClick={(e) => e.stopPropagation()}
                    className="ml-1 underline hover:no-underline"
                  >
                    <ExternalLink className="h-3 w-3 inline" />
                  </Link>
                )}
              </span>
            )}

            {hasContent ? (
              <span className="flex items-center gap-1">
                <FileText className="h-3 w-3" />
                Has content
              </span>
            ) : (
              !draftStatusDisplay && (
                <span className="flex items-center gap-1 text-amber-600 dark:text-amber-400">
                  <FileText className="h-3 w-3" />
                  No content
                </span>
              )
            )}

            {resourceCount > 0 && (
              <span className="flex items-center gap-1">
                <FolderOpen className="h-3 w-3" />
                {resourceCount} resource{resourceCount !== 1 ? 's' : ''}
              </span>
            )}

            {/* Show error tooltip on hover */}
            {skill.draft_status === 'error' && skill.draft_error && (
              <span
                className="text-red-600 dark:text-red-400 truncate max-w-[200px]"
                title={skill.draft_error}
              >
                {skill.draft_error.slice(0, 50)}...
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Delete confirmation dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Skill</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;{skill.name}&quot;? This action cannot
              be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={handleDelete}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

export default SkillCard;
