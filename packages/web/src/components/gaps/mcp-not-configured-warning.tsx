'use client';

import Link from 'next/link';
import type { Route } from 'next';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { AlertTriangle, Plug } from 'lucide-react';

interface McpNotConfiguredWarningProps {
  projectSlug: string;
  mcpKey: string;
}

/**
 * Inline warning shown on a covered_by_mcp gap when the referenced
 * MCP key is not configured for the current project.
 *
 * Provides a one-click CTA that navigates to the MCP Integrations page
 * with `?add=<mcpKey>` so the dialog opens pre-selected.
 */
export function McpNotConfiguredWarning({
  projectSlug,
  mcpKey,
}: McpNotConfiguredWarningProps) {
  const href =
    `/projects/${projectSlug}/mcp-integrations?add=${encodeURIComponent(mcpKey)}` as Route;
  return (
    <Alert
      variant="default"
      className="border-amber-500/50 bg-amber-500/10 text-amber-900 dark:border-amber-500/40 dark:text-amber-200"
    >
      <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
      <AlertTitle className="text-sm font-medium">
        MCP not configured
      </AlertTitle>
      <AlertDescription className="flex flex-wrap items-center gap-3 text-xs">
        <span>
          This gap references <code className="rounded bg-background/50 px-1 py-0.5 text-[11px] font-mono">{mcpKey}</code>,
          but it is not configured for this project yet.
        </span>
        <Button asChild size="sm" variant="outline" className="h-7">
          <Link href={href}>
            <Plug className="mr-1.5 h-3.5 w-3.5" />
            Configure now
          </Link>
        </Button>
      </AlertDescription>
    </Alert>
  );
}
