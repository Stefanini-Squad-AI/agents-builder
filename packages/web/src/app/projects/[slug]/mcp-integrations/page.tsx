'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowLeft, Plug } from 'lucide-react';
import { useProject } from '@/lib/api/queries/use-projects';
import { useMcpConfigs } from '@/lib/api/queries/use-mcp';
import {
  ConfiguredList,
  CatalogBrowser,
  AddMcpDialog,
  EditConfigDialog,
  ExportPanel,
} from '@/components/mcp';

interface McpIntegrationsPageProps {
  params: { slug: string };
}

type TabValue = 'configured' | 'catalog' | 'export';

export default function McpIntegrationsPage({
  params,
}: McpIntegrationsPageProps) {
  const projectSlug = params.slug;
  const searchParams = useSearchParams();
  const addKeyParam = searchParams.get('add');

  const [tab, setTab] = useState<TabValue>('configured');
  const [addMcpKey, setAddMcpKey] = useState<string | null>(null);
  const [editingConfigId, setEditingConfigId] = useState<string | null>(null);

  const { data: project, isLoading: projectLoading } = useProject(projectSlug);
  const { data: configs } = useMcpConfigs(project?.id ?? '', false, !!project?.id);

  // Auto-open AddMcpDialog when ?add=<key> is present in URL
  useEffect(() => {
    if (addKeyParam && project?.id) {
      setAddMcpKey(addKeyParam);
      setTab('catalog');
    }
  }, [addKeyParam, project?.id]);

  return (
    <div className="container mx-auto space-y-6 py-6">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-4">
        <Button variant="ghost" size="sm" asChild>
          <Link href={`/projects/${projectSlug}`}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to project
          </Link>
        </Button>
        <div className="h-6 w-px bg-border" />
        <div className="flex items-center gap-2">
          <Plug className="h-5 w-5 text-primary" />
          <h1 className="text-xl font-semibold">MCP Integrations</h1>
        </div>
        {project && (
          <span className="text-sm text-muted-foreground">— {project.name}</span>
        )}
      </div>

      <p className="text-sm text-muted-foreground max-w-3xl">
        Configure MCP (Model Context Protocol) servers for this project. Add
        servers from the catalog, manage their secrets and settings, and export
        a ready-to-use <code className="font-mono text-xs">.cursor/mcp.json</code> file.
      </p>

      {projectLoading ? (
        <Skeleton className="h-10 w-80 rounded" />
      ) : !project?.id ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
          Project not found.
        </div>
      ) : (
        <Tabs value={tab} onValueChange={(v) => setTab(v as TabValue)}>
          <TabsList>
            <TabsTrigger value="configured">
              Configured
              {configs && configs.length > 0 && (
                <span className="ml-2 rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">
                  {configs.length}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="catalog">Catalog</TabsTrigger>
            <TabsTrigger value="export">Export</TabsTrigger>
          </TabsList>

          <TabsContent value="configured" className="mt-6">
            <ConfiguredList
              projectId={project.id}
              onEdit={(configId) => setEditingConfigId(configId)}
            />
          </TabsContent>

          <TabsContent value="catalog" className="mt-6">
            <CatalogBrowser
              configs={configs}
              onConfigure={(key) => setAddMcpKey(key)}
            />
          </TabsContent>

          <TabsContent value="export" className="mt-6">
            <ExportPanel projectId={project.id} />
          </TabsContent>
        </Tabs>
      )}

      {project?.id && (
        <>
          <AddMcpDialog
            open={addMcpKey !== null}
            onOpenChange={(o) => !o && setAddMcpKey(null)}
            projectId={project.id}
            mcpKey={addMcpKey}
          />
          <EditConfigDialog
            open={editingConfigId !== null}
            onOpenChange={(o) => !o && setEditingConfigId(null)}
            projectId={project.id}
            configId={editingConfigId}
          />
        </>
      )}
    </div>
  );
}
