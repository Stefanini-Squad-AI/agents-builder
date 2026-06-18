'use client';

import { useParams, useRouter } from 'next/navigation';
import type { Route } from 'next';
import { useProject } from '@/lib/api/queries/use-projects';
import { useProjectArtifacts } from '@/lib/api/queries/use-artifacts';
import { useQaStats, useProjectReadiness } from '@/lib/api/queries/use-qa';
import { useProjectTechChoices } from '@/lib/api/queries/use-tech';
import { useGapsStats } from '@/lib/api/queries/use-gaps';
import { useMcpConfigs } from '@/lib/api/queries/use-mcp';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { 
  ArrowLeft, 
  Loader2, 
  LayoutList, 
  Lightbulb, 
  GitBranch, 
  FileDown,
  Settings2,
  CheckCircle2,
  AlertCircle,
  FileText,
  MessageSquare,
  Layers,
  Network,
  FlaskConical,
  AlertOctagon,
  Plug,
} from 'lucide-react';
import { ProjectType } from '@/lib/api/types';
import Link from 'next/link';

/**
 * Project detail page - shows project overview with navigation tabs.
 */
export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectSlug = params.slug as string;

  const { data: project, isLoading, error } = useProject(projectSlug);
  const { data: artifacts } = useProjectArtifacts(projectSlug);
  const { data: qaStats } = useQaStats(projectSlug);
  const { data: techChoices } = useProjectTechChoices(projectSlug);
  const { data: readiness } = useProjectReadiness(projectSlug);
  const { data: gapsStats } = useGapsStats(projectSlug);
  const { data: mcpConfigs } = useMcpConfigs(project?.id ?? '', false, !!project?.id);
  const enabledMcpCount = (mcpConfigs ?? []).filter((c) => c.enabled).length;
  const openGapsCount = gapsStats?.open ?? 0;

  // Calculate setup progress
  const artifactCount = artifacts?.length || 0;
  const qaAnswered = qaStats?.answered_questions || 0;
  const qaTotal = qaStats?.total_questions || 7;
  const techCount = techChoices?.length || 0;
  const isSetupComplete = readiness?.ready ?? false;
  
  // Calculate overall progress (artifacts optional, qa required, tech optional)
  const setupProgress = Math.round(
    ((artifactCount > 0 ? 25 : 0) + 
     ((qaStats?.required_percentage || 0) * 0.5) + 
     (techCount > 0 ? 25 : 0))
  );

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <div className="text-center space-y-4">
          <h2 className="text-xl font-semibold">Project not found</h2>
          <p className="text-muted-foreground">
            The project &quot;{projectSlug}&quot; could not be loaded.
          </p>
          <Button variant="outline" onClick={() => router.push('/projects')}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Projects
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => router.push('/projects')}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Projects
        </Button>
        <div className="h-6 w-px bg-border" />
        <div>
          <h1 className="text-2xl font-bold">{project.name}</h1>
          <p className="text-muted-foreground text-sm">{project.slug}</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {project.project_type === ProjectType.MIGRATION && (
            <Badge variant="secondary" className="gap-1">
              <FlaskConical className="h-3 w-3" />
              ETL Migration
            </Badge>
          )}
          <Badge variant="outline">{project.status}</Badge>
        </div>
      </div>

      {/* Project Info */}
      <Card>
        <CardHeader>
          <CardTitle>Objective</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground whitespace-pre-wrap">
            {project.objective || 'No objective set'}
          </p>
        </CardContent>
      </Card>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{project.llm_provider}</div>
            <p className="text-xs text-muted-foreground">LLM Provider</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold truncate">{project.llm_model}</div>
            <p className="text-xs text-muted-foreground">Model</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{project.card_template}</div>
            <p className="text-xs text-muted-foreground">Template</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{project.card_code_prefix}</div>
            <p className="text-xs text-muted-foreground">Code Prefix</p>
          </CardContent>
        </Card>
      </div>

      {/* Setup Progress */}
      <Card className={isSetupComplete ? 'border-green-500/50 bg-green-500/5' : 'border-yellow-500/50 bg-yellow-500/5'}>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {isSetupComplete ? (
                <CheckCircle2 className="h-5 w-5 text-green-500" />
              ) : (
                <Settings2 className="h-5 w-5 text-yellow-500" />
              )}
              <CardTitle className="text-base">Project Setup</CardTitle>
            </div>
            <Link href={`/projects/${projectSlug}/setup`}>
              <Button variant={isSetupComplete ? "outline" : "default"} size="sm">
                {isSetupComplete ? 'Review Setup' : 'Continue Setup'}
              </Button>
            </Link>
          </div>
          {!isSetupComplete && (
            <CardDescription>
              Complete project setup to enable AI-powered skill and backlog generation
            </CardDescription>
          )}
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Progress bar */}
            <div className="flex items-center gap-4">
              <Progress value={setupProgress} className="flex-1" />
              <span className="text-sm text-muted-foreground w-12 text-right">
                {setupProgress}%
              </span>
            </div>
            
            {/* Setup items */}
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-muted-foreground" />
                <span className={artifactCount > 0 ? 'text-foreground' : 'text-muted-foreground'}>
                  {artifactCount} Artifacts
                </span>
                {artifactCount > 0 && <CheckCircle2 className="h-3 w-3 text-green-500" />}
              </div>
              <div className="flex items-center gap-2">
                <MessageSquare className="h-4 w-4 text-muted-foreground" />
                <span className={qaAnswered > 0 ? 'text-foreground' : 'text-muted-foreground'}>
                  {qaAnswered}/{qaTotal} Q&A
                </span>
                {qaStats?.required_percentage === 100 && <CheckCircle2 className="h-3 w-3 text-green-500" />}
              </div>
              <div className="flex items-center gap-2">
                <Layers className="h-4 w-4 text-muted-foreground" />
                <span className={techCount > 0 ? 'text-foreground' : 'text-muted-foreground'}>
                  {techCount} Tech
                </span>
                {techCount > 0 && <CheckCircle2 className="h-3 w-3 text-green-500" />}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Navigation — adapts to project type */}
      {project.project_type === ProjectType.MIGRATION ? (
        /* Migration Workbench navigation */
        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Migration Workbench
          </p>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <Link href={`/projects/${projectSlug}/map`}>
              <Card className="hover:bg-accent cursor-pointer transition-colors border-primary/30">
                <CardContent className="pt-6 flex items-center gap-3">
                  <Network className="h-5 w-5 text-primary" />
                  <div>
                    <div className="font-medium">Migration Map</div>
                    <div className="text-xs text-muted-foreground">Packages, flows, waves</div>
                  </div>
                </CardContent>
              </Card>
            </Link>
            <Link href={`/projects/${projectSlug}/skills`}>
              <Card className="hover:bg-accent cursor-pointer transition-colors">
                <CardContent className="pt-6 flex items-center gap-3">
                  <Lightbulb className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <div className="font-medium">Skills</div>
                    <div className="text-xs text-muted-foreground">Migration skill library</div>
                  </div>
                </CardContent>
              </Card>
            </Link>
            <Link href={`/projects/${projectSlug}/backlog`}>
              <Card className="hover:bg-accent cursor-pointer transition-colors">
                <CardContent className="pt-6 flex items-center gap-3">
                  <LayoutList className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <div className="font-medium">Backlog</div>
                    <div className="text-xs text-muted-foreground">Migration cards</div>
                  </div>
                </CardContent>
              </Card>
            </Link>
            <Link href={`/projects/${projectSlug}/dag`}>
              <Card className="hover:bg-accent cursor-pointer transition-colors">
                <CardContent className="pt-6 flex items-center gap-3">
                  <GitBranch className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <div className="font-medium">DAG</div>
                    <div className="text-xs text-muted-foreground">Card dependencies</div>
                  </div>
                </CardContent>
              </Card>
            </Link>
            <Link href={`/projects/${projectSlug}/llm-runs`}>
              <Card className="hover:bg-accent cursor-pointer transition-colors">
                <CardContent className="pt-6 flex items-center gap-3">
                  <AlertCircle className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <div className="font-medium">LLM Runs</div>
                    <div className="text-xs text-muted-foreground">Audit trail &amp; cost</div>
                  </div>
                </CardContent>
              </Card>
            </Link>
            <Link href={`/projects/${projectSlug}/gaps` as Route}>
              <Card className="hover:bg-accent cursor-pointer transition-colors">
                <CardContent className="pt-6 flex items-center gap-3">
                  <AlertOctagon className="h-5 w-5 text-muted-foreground" />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">Coverage Gaps</span>
                      {openGapsCount > 0 && (
                        <Badge
                          variant="outline"
                          className="border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400"
                        >
                          {openGapsCount} open
                        </Badge>
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground">Decide skill / MCP / OOS</div>
                  </div>
                </CardContent>
              </Card>
            </Link>
            <Link href={`/projects/${projectSlug}/mcp-integrations` as Route}>
              <Card className="hover:bg-accent cursor-pointer transition-colors">
                <CardContent className="pt-6 flex items-center gap-3">
                  <Plug className="h-5 w-5 text-muted-foreground" />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">MCP Integrations</span>
                      {enabledMcpCount > 0 && (
                        <Badge variant="secondary">{enabledMcpCount}</Badge>
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground">Configure &amp; export mcp.json</div>
                  </div>
                </CardContent>
              </Card>
            </Link>
            <Link href={`/projects/${projectSlug}/export`}>
              <Card className="hover:bg-accent cursor-pointer transition-colors">
                <CardContent className="pt-6 flex items-center gap-3">
                  <FileDown className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <div className="font-medium">Export</div>
                    <div className="text-xs text-muted-foreground">ZIP, Jira CSV</div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          </div>
        </div>
      ) : (
        /* Application development navigation */
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <Link href={`/projects/${projectSlug}/backlog`}>
            <Card className="hover:bg-accent cursor-pointer transition-colors">
              <CardContent className="pt-6 flex items-center gap-3">
                <LayoutList className="h-5 w-5 text-muted-foreground" />
                <span className="font-medium">Backlog</span>
              </CardContent>
            </Card>
          </Link>
          <Link href={`/projects/${projectSlug}/skills`}>
            <Card className="hover:bg-accent cursor-pointer transition-colors">
              <CardContent className="pt-6 flex items-center gap-3">
                <Lightbulb className="h-5 w-5 text-muted-foreground" />
                <span className="font-medium">Skills</span>
              </CardContent>
            </Card>
          </Link>
          <Link href={`/projects/${projectSlug}/dag`}>
            <Card className="hover:bg-accent cursor-pointer transition-colors">
              <CardContent className="pt-6 flex items-center gap-3">
                <GitBranch className="h-5 w-5 text-muted-foreground" />
                <span className="font-medium">DAG</span>
              </CardContent>
            </Card>
          </Link>
          <Link href={`/projects/${projectSlug}/gaps` as Route}>
            <Card className="hover:bg-accent cursor-pointer transition-colors">
              <CardContent className="pt-6 flex items-center gap-3">
                <AlertOctagon className="h-5 w-5 text-muted-foreground" />
                <span className="font-medium">Coverage Gaps</span>
                {openGapsCount > 0 && (
                  <Badge
                    variant="outline"
                    className="ml-auto border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400"
                  >
                    {openGapsCount}
                  </Badge>
                )}
              </CardContent>
            </Card>
          </Link>
          <Link href={`/projects/${projectSlug}/mcp-integrations` as Route}>
            <Card className="hover:bg-accent cursor-pointer transition-colors">
              <CardContent className="pt-6 flex items-center gap-3">
                <Plug className="h-5 w-5 text-muted-foreground" />
                <span className="font-medium">MCP Integrations</span>
                {enabledMcpCount > 0 && (
                  <Badge variant="secondary" className="ml-auto">
                    {enabledMcpCount}
                  </Badge>
                )}
              </CardContent>
            </Card>
          </Link>
          <Link href={`/projects/${projectSlug}/export`}>
            <Card className="hover:bg-accent cursor-pointer transition-colors">
              <CardContent className="pt-6 flex items-center gap-3">
                <FileDown className="h-5 w-5 text-muted-foreground" />
                <span className="font-medium">Export</span>
              </CardContent>
            </Card>
          </Link>
        </div>
      )}
    </div>
  );
}
