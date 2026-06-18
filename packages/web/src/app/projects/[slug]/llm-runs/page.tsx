'use client';

import { useParams, useRouter } from 'next/navigation';
import { useState, useCallback } from 'react';
import { useLlmRuns, useLlmRunsStats, useLlmRunDetails } from '@/lib/api/queries';
import { LlmRunView, LlmRunKind, LlmRunStatus } from '@/lib/api/types';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  ArrowLeft,
  Bot,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  DollarSign,
  Zap,
  ChevronLeft,
  ChevronRight,
  Loader2,
  RefreshCw,
  Sparkles,
} from 'lucide-react';

const KIND_LABELS: Record<string, string> = {
  propose_skill_set: 'Propose Skills',
  draft_skill_body: 'Draft Skill',
  propose_backlog: 'Propose Backlog',
  draft_card: 'Draft Card',
  suggest_tech: 'Suggest Tech',
  other: 'Other',
};

const STATUS_CONFIG: Record<string, { icon: typeof CheckCircle2; color: string; label: string }> = {
  success: { icon: CheckCircle2, color: 'text-green-500', label: 'Success' },
  parse_error: { icon: AlertTriangle, color: 'text-yellow-500', label: 'Parse Error' },
  provider_error: { icon: XCircle, color: 'text-red-500', label: 'Provider Error' },
  in_progress: { icon: Clock, color: 'text-blue-500', label: 'In Progress' },
};

function formatCost(cost: number | undefined | null): string {
  if (!cost) return '-';
  return `$${cost.toFixed(4)}`;
}

function formatTokens(tokens: number | undefined | null): string {
  if (!tokens) return '-';
  return tokens.toLocaleString();
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleString();
}

export default function LlmRunsPage() {
  const params = useParams();
  const router = useRouter();
  const projectSlug = params.slug as string;

  // State
  const [kindFilter, setKindFilter] = useState<string>('all');
  const [page, setPage] = useState(0);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const pageSize = 20;

  // Queries
  const { data: stats, isLoading: isLoadingStats, refetch: refetchStats } = useLlmRunsStats(projectSlug);
  const { data: runsData, isLoading: isLoadingRuns, refetch: refetchRuns } = useLlmRuns(
    projectSlug,
    {
      kind: kindFilter !== 'all' ? kindFilter : undefined,
      limit: pageSize,
      offset: page * pageSize,
    }
  );
  const { data: runDetails, isLoading: isLoadingDetails } = useLlmRunDetails(
    selectedRunId || '',
    !!selectedRunId
  );

  const handleRefresh = useCallback(() => {
    refetchStats();
    refetchRuns();
  }, [refetchStats, refetchRuns]);

  const totalPages = runsData ? Math.ceil(runsData.total / pageSize) : 0;

  return (
    <div className="container mx-auto py-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push(`/projects/${projectSlug}` as any)}
          >
            <ArrowLeft className="h-4 w-4 sm:mr-2" />
            <span className="hidden sm:inline">Back to Project</span>
          </Button>
          <div className="hidden sm:block h-6 w-px bg-border" />
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-muted-foreground" />
            <h1 className="text-xl sm:text-2xl font-bold">LLM Runs Audit</h1>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefresh}
          disabled={isLoadingStats || isLoadingRuns}
        >
          <RefreshCw className={`h-4 w-4 sm:mr-2 ${isLoadingStats || isLoadingRuns ? 'animate-spin' : ''}`} />
          <span className="hidden sm:inline">Refresh</span>
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Runs</CardDescription>
            <CardTitle className="text-3xl">
              {isLoadingStats ? <Loader2 className="h-6 w-6 animate-spin" /> : stats?.total_runs || 0}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-1">
              <DollarSign className="h-3 w-3" /> Total Cost
            </CardDescription>
            <CardTitle className="text-3xl">
              {isLoadingStats ? (
                <Loader2 className="h-6 w-6 animate-spin" />
              ) : (
                `$${(stats?.total_cost_usd || 0).toFixed(4)}`
              )}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-1">
              <Zap className="h-3 w-3" /> Tokens In
            </CardDescription>
            <CardTitle className="text-3xl">
              {isLoadingStats ? (
                <Loader2 className="h-6 w-6 animate-spin" />
              ) : (
                (stats?.total_tokens_in || 0).toLocaleString()
              )}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-1">
              <Zap className="h-3 w-3" /> Tokens Out
            </CardDescription>
            <CardTitle className="text-3xl">
              {isLoadingStats ? (
                <Loader2 className="h-6 w-6 animate-spin" />
              ) : (
                (stats?.total_tokens_out || 0).toLocaleString()
              )}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Filter + Table */}
      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <CardTitle>Run History</CardTitle>
            <Select value={kindFilter} onValueChange={setKindFilter}>
              <SelectTrigger className="w-full sm:w-48">
                <SelectValue placeholder="Filter by kind" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Kinds</SelectItem>
                {Object.entries(KIND_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          {isLoadingRuns ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : !runsData?.runs.length ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Bot className="h-16 w-16 text-muted-foreground/40 mb-4" />
              <h3 className="text-lg font-semibold mb-2">No LLM Runs Yet</h3>
              <p className="text-muted-foreground max-w-sm mb-4">
                LLM runs will appear here when you use AI features like proposing skills,
                generating cards, or suggesting tech stack.
              </p>
              <Button
                variant="outline"
                onClick={() => router.push(`/projects/${projectSlug}/skills` as any)}
              >
                <Sparkles className="mr-2 h-4 w-4" />
                Go to Skills
              </Button>
            </div>
          ) : (
            <>
              {/* Mobile card view */}
              <div className="md:hidden space-y-3">
                {runsData.runs.map((run) => {
                  const statusConfig = STATUS_CONFIG[run.status] || STATUS_CONFIG.success;
                  const StatusIcon = statusConfig.icon;
                  return (
                    <div
                      key={run.id}
                      className="p-4 border rounded-lg cursor-pointer hover:bg-muted/50 space-y-3"
                      onClick={() => setSelectedRunId(run.id)}
                    >
                      <div className="flex items-center justify-between">
                        <Badge variant="outline">{KIND_LABELS[run.kind] || run.kind}</Badge>
                        <div className="flex items-center gap-1">
                          <StatusIcon className={`h-4 w-4 ${statusConfig.color}`} />
                          <span className="text-sm">{statusConfig.label}</span>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        <div>
                          <span className="text-muted-foreground">Provider:</span>
                          <span className="ml-1 capitalize">{run.provider}</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Cost:</span>
                          <span className="ml-1 font-mono">{formatCost(run.cost_usd as number)}</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Tokens:</span>
                          <span className="ml-1 font-mono">{formatTokens((run.tokens_in || 0) + (run.tokens_out || 0))}</span>
                        </div>
                        <div className="text-muted-foreground text-xs">
                          {formatDate(run.created_at)}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Desktop table view */}
              <div className="hidden md:block overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>ID</TableHead>
                      <TableHead>Kind</TableHead>
                      <TableHead>Provider</TableHead>
                      <TableHead>Model</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Tokens</TableHead>
                      <TableHead className="text-right">Cost</TableHead>
                      <TableHead>Created</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {runsData.runs.map((run) => {
                      const statusConfig = STATUS_CONFIG[run.status] || STATUS_CONFIG.success;
                      const StatusIcon = statusConfig.icon;
                      return (
                        <TableRow
                          key={run.id}
                          className="cursor-pointer hover:bg-muted/50"
                          onClick={() => setSelectedRunId(run.id)}
                        >
                          <TableCell className="font-mono text-xs">
                            {run.id.slice(0, 8)}...
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">
                              {KIND_LABELS[run.kind] || run.kind}
                            </Badge>
                          </TableCell>
                          <TableCell className="capitalize">{run.provider}</TableCell>
                          <TableCell className="font-mono text-xs">{run.model}</TableCell>
                          <TableCell>
                            <div className="flex items-center gap-1">
                              <StatusIcon className={`h-4 w-4 ${statusConfig.color}`} />
                              <span className="text-sm">{statusConfig.label}</span>
                            </div>
                          </TableCell>
                          <TableCell className="text-right font-mono text-sm">
                            {formatTokens((run.tokens_in || 0) + (run.tokens_out || 0))}
                          </TableCell>
                          <TableCell className="text-right font-mono text-sm">
                            {formatCost(run.cost_usd as number)}
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {formatDate(run.created_at)}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4">
                  <p className="text-sm text-muted-foreground">
                    Showing {page * pageSize + 1}-{Math.min((page + 1) * pageSize, runsData.total)} of {runsData.total}
                  </p>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.max(0, p - 1))}
                      disabled={page === 0}
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <span className="text-sm">
                      Page {page + 1} of {totalPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                      disabled={page >= totalPages - 1}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Run Details Drawer */}
      <Sheet open={!!selectedRunId} onOpenChange={(open) => !open && setSelectedRunId(null)}>
        <SheetContent className="w-full sm:max-w-2xl overflow-y-auto">
          <SheetHeader>
            <SheetTitle>LLM Run Details</SheetTitle>
            <SheetDescription>
              {selectedRunId && `ID: ${selectedRunId}`}
            </SheetDescription>
          </SheetHeader>
          
          {isLoadingDetails ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : runDetails ? (
            <div className="mt-6 space-y-6">
              {/* Run Info */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Kind</p>
                  <p>{KIND_LABELS[runDetails.run.kind] || runDetails.run.kind}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Status</p>
                  <div className="flex items-center gap-1">
                    {(() => {
                      const config = STATUS_CONFIG[runDetails.run.status];
                      const Icon = config.icon;
                      return (
                        <>
                          <Icon className={`h-4 w-4 ${config.color}`} />
                          <span>{config.label}</span>
                        </>
                      );
                    })()}
                  </div>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Provider</p>
                  <p className="capitalize">{runDetails.run.provider}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Model</p>
                  <p className="font-mono text-sm">{runDetails.run.model}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Tokens</p>
                  <p>
                    {formatTokens(runDetails.run.tokens_in)} in / {formatTokens(runDetails.run.tokens_out)} out
                  </p>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Cost</p>
                  <p>{formatCost(runDetails.run.cost_usd as number)}</p>
                </div>
              </div>

              {/* Error if any */}
              {runDetails.run.error && (
                <>
                  <Separator />
                  <div>
                    <p className="text-sm font-medium text-red-500 mb-2">Error</p>
                    <pre className="bg-red-50 dark:bg-red-950 p-3 rounded-lg text-sm overflow-x-auto">
                      {runDetails.run.error}
                    </pre>
                  </div>
                </>
              )}

              <Separator />

              {/* System Prompt */}
              {runDetails.prompt.system && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground mb-2">System Prompt</p>
                  <ScrollArea className="h-40 border rounded-lg">
                    <pre className="p-3 text-sm whitespace-pre-wrap">
                      {runDetails.prompt.system}
                    </pre>
                  </ScrollArea>
                </div>
              )}

              {/* Messages */}
              {runDetails.prompt.messages.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground mb-2">Messages</p>
                  <div className="space-y-2">
                    {runDetails.prompt.messages.map((msg, i) => (
                      <div key={i} className="border rounded-lg p-3">
                        <Badge variant="outline" className="mb-2 capitalize">
                          {msg.role}
                        </Badge>
                        <ScrollArea className="max-h-40">
                          <pre className="text-sm whitespace-pre-wrap">{msg.content}</pre>
                        </ScrollArea>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <Separator />

              {/* Response */}
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-2">Response</p>
                <ScrollArea className="h-60 border rounded-lg">
                  {runDetails.response.json ? (
                    <pre className="p-3 text-sm">
                      {JSON.stringify(runDetails.response.json, null, 2)}
                    </pre>
                  ) : runDetails.response.text ? (
                    <pre className="p-3 text-sm whitespace-pre-wrap">
                      {runDetails.response.text}
                    </pre>
                  ) : (
                    <p className="p-3 text-sm text-muted-foreground">No response</p>
                  )}
                </ScrollArea>
              </div>

              {/* Reasoning (if any) */}
              {runDetails.response.reasoning && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground mb-2">
                    Reasoning {runDetails.run.reasoning_truncated && '(truncated)'}
                  </p>
                  <ScrollArea className="h-40 border rounded-lg bg-purple-50 dark:bg-purple-950">
                    <pre className="p-3 text-sm whitespace-pre-wrap">
                      {runDetails.response.reasoning}
                    </pre>
                  </ScrollArea>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              Select a run to view details
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
