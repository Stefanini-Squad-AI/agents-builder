'use client';

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { 
  Loader2, 
  Sparkles, 
  Download, 
  FileCode2, 
  Check, 
  AlertTriangle,
  FileText,
  Layers,
  Compass,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { 
  useGenerationPreview, 
  useGeneratePackage, 
  useDownloadBundle 
} from '@/lib/api/queries/use-generation';
import { DesignGuidancePanel } from './design-guidance-panel';
import type { 
  GenerationStrategy, 
  GenerationOptions, 
  GeneratedArtifact,
  GenerationResult,
} from '@/lib/api/types';

interface GenerationDialogProps {
  projectSlug: string;
  packageId: string;
  packageName: string;
  trigger?: React.ReactNode;
}

const strategyLabels: Record<GenerationStrategy, string> = {
  sql: 'SQL Notebook',
  pyspark: 'PySpark',
  hybrid: 'Hybrid (Single)',
  modular: 'Modular (Orchestrator + SQL)',
};

const strategyIcons: Record<GenerationStrategy, React.ElementType> = {
  sql: FileCode2,
  pyspark: FileCode2,
  hybrid: FileCode2,
  modular: Layers,
};

export function GenerationDialog({
  projectSlug,
  packageId,
  packageName,
  trigger,
}: GenerationDialogProps) {
  const [open, setOpen] = useState(false);
  const [options, setOptions] = useState<GenerationOptions>({
    target_catalog: 'main',
    target_schema: 'default',
    include_comments: true,
    include_docstring_header: true,
    include_validation_cells: true,
    enable_photon_hints: true,
    use_delta_merge: true,
  });
  const [result, setResult] = useState<GenerationResult | null>(null);

  const { data: preview, isLoading: previewLoading } = useGenerationPreview(
    projectSlug,
    packageId
  );

  const generateMutation = useGeneratePackage(projectSlug);
  const downloadMutation = useDownloadBundle(projectSlug);

  const handleGenerate = async () => {
    try {
      const res = await generateMutation.mutateAsync({ packageId, options });
      setResult(res);
    } catch (error) {
      console.error('Generation failed:', error);
    }
  };

  const handleDownload = () => {
    downloadMutation.mutate({ packageId, options });
  };

  const handleForceStrategy = (value: string) => {
    setOptions((prev) => ({
      ...prev,
      force_strategy: value === 'auto' ? undefined : (value as GenerationStrategy),
    }));
  };

  const isGenerating = generateMutation.isPending;
  const isDownloading = downloadMutation.isPending;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger || (
          <Button variant="default" size="sm" className="gap-2">
            <Sparkles className="h-4 w-4" />
            Generate
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5" />
            Generate Databricks Notebooks
          </DialogTitle>
          <DialogDescription>
            Generate production-ready Databricks notebooks for{' '}
            <span className="font-medium">{packageName}</span>
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue={result ? 'result' : 'design'} className="flex-1 overflow-hidden flex flex-col">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="design" className="gap-1">
              <Compass className="h-3 w-3" />
              Design
            </TabsTrigger>
            <TabsTrigger value="preview">Preview</TabsTrigger>
            <TabsTrigger value="options">Options</TabsTrigger>
            <TabsTrigger value="result" disabled={!result}>
              Result {result && <Check className="h-3 w-3 ml-1" />}
            </TabsTrigger>
          </TabsList>

          {/* Design Tab - Pattern Analysis */}
          <TabsContent value="design" className="flex-1 overflow-hidden">
            <ScrollArea className="h-[350px] pr-4">
              <DesignGuidancePanel
                projectSlug={projectSlug}
                packageId={packageId}
              />
            </ScrollArea>
          </TabsContent>

          {/* Preview Tab */}
          <TabsContent value="preview" className="flex-1 overflow-hidden">
            <ScrollArea className="h-[350px] pr-4">
              {previewLoading ? (
                <div className="flex items-center justify-center h-32">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : preview ? (
                <div className="space-y-4">
                  {/* Strategy */}
                  <div className="space-y-2">
                    <Label>Recommended Strategy</Label>
                    <div className="flex items-center gap-2">
                      {(() => {
                        const Icon = strategyIcons[preview.strategy];
                        return <Icon className="h-4 w-4 text-muted-foreground" />;
                      })()}
                      <Badge variant="secondary">
                        {strategyLabels[preview.strategy]}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {preview.rationale}
                    </p>
                  </div>

                  <Separator />

                  {/* Planned Artifacts */}
                  <div className="space-y-2">
                    <Label>Planned Artifacts ({preview.planned_artifacts.length})</Label>
                    <div className="space-y-2">
                      {preview.planned_artifacts.map((artifact, idx) => (
                        <div
                          key={idx}
                          className="flex items-start gap-3 p-3 rounded-md border bg-muted/30"
                        >
                          <FileText className="h-4 w-4 mt-0.5 text-muted-foreground" />
                          <div className="flex-1 min-w-0">
                            <div className="font-mono text-sm truncate">
                              {artifact.name}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {artifact.purpose}
                            </div>
                          </div>
                          <Badge variant="outline" className="text-xs">
                            {artifact.tier}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-center h-32 text-muted-foreground">
                  Failed to load preview
                </div>
              )}
            </ScrollArea>
          </TabsContent>

          {/* Options Tab */}
          <TabsContent value="options" className="flex-1 overflow-hidden">
            <ScrollArea className="h-[350px] pr-4">
              <div className="space-y-6">
                {/* Target */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="catalog">Unity Catalog</Label>
                    <Input
                      id="catalog"
                      value={options.target_catalog}
                      onChange={(e) =>
                        setOptions((p) => ({ ...p, target_catalog: e.target.value }))
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="schema">Target Schema</Label>
                    <Input
                      id="schema"
                      value={options.target_schema}
                      onChange={(e) =>
                        setOptions((p) => ({ ...p, target_schema: e.target.value }))
                      }
                    />
                  </div>
                </div>

                <Separator />

                {/* Strategy Override */}
                <div className="space-y-2">
                  <Label>Generation Strategy</Label>
                  <Select
                    value={options.force_strategy || 'auto'}
                    onValueChange={handleForceStrategy}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Auto (use backward analysis)" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="auto">Auto (recommended)</SelectItem>
                      <SelectItem value="sql">SQL Notebook</SelectItem>
                      <SelectItem value="pyspark">PySpark</SelectItem>
                      <SelectItem value="modular">Modular (Orchestrator + SQL)</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    Override the classifier's strategy recommendation
                  </p>
                </div>

                <Separator />

                {/* Toggles */}
                <div className="space-y-4">
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="comments"
                      checked={options.include_comments}
                      onCheckedChange={(c) =>
                        setOptions((p) => ({ ...p, include_comments: !!c }))
                      }
                    />
                    <Label htmlFor="comments">Include explanatory comments</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="docstring"
                      checked={options.include_docstring_header}
                      onCheckedChange={(c) =>
                        setOptions((p) => ({ ...p, include_docstring_header: !!c }))
                      }
                    />
                    <Label htmlFor="docstring">Include header docstring</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="validation"
                      checked={options.include_validation_cells}
                      onCheckedChange={(c) =>
                        setOptions((p) => ({ ...p, include_validation_cells: !!c }))
                      }
                    />
                    <Label htmlFor="validation">Include validation cells</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="photon"
                      checked={options.enable_photon_hints}
                      onCheckedChange={(c) =>
                        setOptions((p) => ({ ...p, enable_photon_hints: !!c }))
                      }
                    />
                    <Label htmlFor="photon">Enable Photon optimization hints</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="merge"
                      checked={options.use_delta_merge}
                      onCheckedChange={(c) =>
                        setOptions((p) => ({ ...p, use_delta_merge: !!c }))
                      }
                    />
                    <Label htmlFor="merge">Prefer Delta MERGE over INSERT/UPDATE</Label>
                  </div>
                </div>
              </div>
            </ScrollArea>
          </TabsContent>

          {/* Result Tab */}
          <TabsContent value="result" className="flex-1 overflow-hidden">
            <ScrollArea className="h-[350px] pr-4">
              {result && (
                <div className="space-y-4">
                  {/* Summary */}
                  <div className="flex items-center gap-4">
                    <Badge
                      variant={result.status === 'success' ? 'default' : 'destructive'}
                      className="gap-1"
                    >
                      {result.status === 'success' ? (
                        <Check className="h-3 w-3" />
                      ) : (
                        <AlertTriangle className="h-3 w-3" />
                      )}
                      {result.status}
                    </Badge>
                    <span className="text-sm text-muted-foreground">
                      {result.total_files} files, {result.total_lines} lines
                    </span>
                    <Badge variant="outline">{strategyLabels[result.strategy]}</Badge>
                  </div>

                  {/* Warnings */}
                  {result.warnings.length > 0 && (
                    <div className="p-3 rounded-md bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800">
                      <div className="flex items-center gap-2 text-amber-800 dark:text-amber-200 font-medium text-sm mb-1">
                        <AlertTriangle className="h-4 w-4" />
                        Warnings
                      </div>
                      <ul className="text-sm text-amber-700 dark:text-amber-300 list-disc list-inside">
                        {result.warnings.map((w, i) => (
                          <li key={i}>{w}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <Separator />

                  {/* Artifacts */}
                  <div className="space-y-2">
                    <Label>Generated Artifacts</Label>
                    <div className="space-y-2">
                      {result.artifacts.map((artifact, idx) => (
                        <ArtifactPreview key={idx} artifact={artifact} />
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </ScrollArea>
          </TabsContent>
        </Tabs>

        <DialogFooter className="gap-2 sm:gap-0">
          {result ? (
            <Button onClick={handleDownload} disabled={isDownloading} className="gap-2">
              {isDownloading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              Download ZIP
            </Button>
          ) : (
            <Button onClick={handleGenerate} disabled={isGenerating} className="gap-2">
              {isGenerating ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              Generate Notebooks
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ArtifactPreview({ artifact }: { artifact: GeneratedArtifact }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-md border overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-3 hover:bg-muted/50 text-left"
      >
        <FileCode2 className="h-4 w-4 text-muted-foreground shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="font-mono text-sm truncate">{artifact.name}</div>
          <div className="text-xs text-muted-foreground">
            {artifact.line_count} lines · {artifact.language}
          </div>
        </div>
        <Badge variant="outline" className="text-xs">
          {artifact.tier}
        </Badge>
      </button>
      {expanded && (
        <div className="border-t bg-muted/30">
          <pre className="p-3 text-xs overflow-x-auto max-h-64">
            <code>{artifact.content}</code>
          </pre>
        </div>
      )}
    </div>
  );
}
