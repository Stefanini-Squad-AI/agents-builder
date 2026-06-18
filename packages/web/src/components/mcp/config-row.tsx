'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
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
import { ValidationBadge } from './validation-badge';
import { MCPConfigSummary } from '@/lib/api/types';
import {
  useToggleMcpConfig,
  useValidateMcpConfig,
  useDeleteMcpConfig,
} from '@/lib/api/queries/use-mcp';
import {
  MoreHorizontal,
  Power,
  Pencil,
  CheckCircle2,
  Trash2,
} from 'lucide-react';

interface ConfigRowProps {
  projectId: string;
  config: MCPConfigSummary;
  onEdit: (configId: string) => void;
}

export function ConfigRow({ projectId, config, onEdit }: ConfigRowProps) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const toggle = useToggleMcpConfig(projectId);
  const validate = useValidateMcpConfig(projectId);
  const remove = useDeleteMcpConfig(projectId);

  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border bg-card p-4">
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <h4 className="text-sm font-medium">{config.mcp_name}</h4>
          <Badge variant="secondary" className="text-xs font-mono">
            {config.mcp_key}
          </Badge>
          <Badge variant="outline" className="text-xs">
            {config.mcp_category.replace('_', ' ')}
          </Badge>
          {!config.enabled && (
            <Badge variant="outline" className="text-xs text-muted-foreground">
              disabled
            </Badge>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <ValidationBadge
            validatedAt={config.validated_at}
            hasError={config.has_validation_error}
          />
          {config.validated_at && (
            <span>
              Last checked {new Date(config.validated_at).toLocaleString()}
            </span>
          )}
        </div>
      </div>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0">
            <MoreHorizontal className="h-4 w-4" />
            <span className="sr-only">Configuration actions</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-52">
          <DropdownMenuItem onClick={() => onEdit(config.id)}>
            <Pencil className="mr-2 h-4 w-4" />
            Edit
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={() =>
              toggle.mutate({ configId: config.id, enabled: !config.enabled })
            }
            disabled={toggle.isPending}
          >
            <Power className="mr-2 h-4 w-4" />
            {config.enabled ? 'Disable' : 'Enable'}
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={() => validate.mutate(config.id)}
            disabled={validate.isPending}
          >
            <CheckCircle2 className="mr-2 h-4 w-4" />
            Validate
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="text-destructive focus:text-destructive"
            onClick={() => setConfirmDelete(true)}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Remove
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove MCP configuration?</AlertDialogTitle>
            <AlertDialogDescription>
              <strong>{config.mcp_name}</strong> will be unconfigured for this
              project. Stored secrets will be deleted. This action cannot be
              undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={remove.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                remove.mutate(config.id, {
                  onSuccess: () => setConfirmDelete(false),
                });
              }}
              disabled={remove.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {remove.isPending ? 'Removing…' : 'Remove'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
