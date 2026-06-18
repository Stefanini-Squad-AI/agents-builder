'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { MCPCatalogListItem } from '@/lib/api/types';
import { CheckCircle2, Plus, Lock, ShieldAlert } from 'lucide-react';

interface CatalogCardProps {
  entry: MCPCatalogListItem;
  isConfigured: boolean;
  onConfigure: (key: string) => void;
}

export function CatalogCard({
  entry,
  isConfigured,
  onConfigure,
}: CatalogCardProps) {
  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <CardTitle className="text-base">{entry.name}</CardTitle>
            <CardDescription className="text-xs">
              {entry.vendor}
            </CardDescription>
          </div>
          <Badge variant="outline" className="shrink-0 text-xs">
            {entry.category.replace('_', ' ')}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col justify-between gap-3">
        <p className="text-sm text-muted-foreground line-clamp-3">
          {entry.description}
        </p>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          {entry.has_secrets && (
            <Badge variant="outline" className="text-amber-700 dark:text-amber-400">
              <Lock className="mr-1 h-3 w-3" />
              secrets
            </Badge>
          )}
          {entry.requires_approval && (
            <Badge variant="outline" className="text-rose-700 dark:text-rose-400">
              <ShieldAlert className="mr-1 h-3 w-3" />
              requires approval
            </Badge>
          )}
          <span className="text-muted-foreground">
            {entry.tool_count} tool{entry.tool_count === 1 ? '' : 's'}
          </span>
        </div>

        <Button
          size="sm"
          variant={isConfigured ? 'outline' : 'default'}
          disabled={isConfigured}
          onClick={() => onConfigure(entry.key)}
        >
          {isConfigured ? (
            <>
              <CheckCircle2 className="mr-2 h-4 w-4" />
              Configured
            </>
          ) : (
            <>
              <Plus className="mr-2 h-4 w-4" />
              Configure
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
