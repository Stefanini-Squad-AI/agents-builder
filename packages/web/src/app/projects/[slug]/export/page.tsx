'use client';

import { useParams, useRouter } from 'next/navigation';
import { useState, useCallback, useEffect } from 'react';
import { useExportPreview, useValidateProject, useExportToZip } from '@/lib/api/queries';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ExportTreeView } from '@/components/export/export-tree-view';
import { ValidationPanel } from '@/components/export/validation-panel';
import { ValidationResponse } from '@/lib/api/types';
import {
  ArrowLeft,
  Download,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
  Package,
} from 'lucide-react';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

export default function ExportPage() {
  const params = useParams();
  const router = useRouter();
  const projectSlug = params.slug as string;

  // State
  const [validation, setValidation] = useState<ValidationResponse | null>(null);
  const [hasValidated, setHasValidated] = useState(false);

  // Queries and mutations
  const { data: preview, isLoading: isLoadingPreview, refetch: refetchPreview } = useExportPreview(projectSlug);
  const validateProject = useValidateProject(projectSlug);
  const exportToZip = useExportToZip(projectSlug);

  // Auto-validate on mount (run once)
  useEffect(() => {
    if (!hasValidated && !validateProject.isPending) {
      setHasValidated(true); // Set first to prevent re-runs
      validateProject.mutate(undefined, {
        onSuccess: (data) => {
          setValidation(data);
        },
        onError: () => {
          setHasValidated(false); // Allow retry on error
        },
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasValidated]);

  // Handle refresh
  const handleRefresh = useCallback(() => {
    refetchPreview();
    validateProject.mutate(undefined, {
      onSuccess: (data) => {
        setValidation(data);
      },
    });
  }, [refetchPreview, validateProject]);

  // Handle export
  const handleExport = useCallback(() => {
    exportToZip.mutate();
  }, [exportToZip]);

  // Determine if export is allowed
  const canExport = validation?.valid || (validation && validation.error_count === 0);

  return (
    <div className="container mx-auto py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push(`/projects/${projectSlug}` as any)}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Project
          </Button>
          <div className="h-6 w-px bg-border" />
          <div className="flex items-center gap-2">
            <Package className="h-5 w-5 text-muted-foreground" />
            <h1 className="text-2xl font-bold">Export Project</h1>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={validateProject.isPending || isLoadingPreview}
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${validateProject.isPending ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Validation Panel */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  {validateProject.isPending ? (
                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                  ) : validation?.valid ? (
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                  ) : validation && validation.error_count > 0 ? (
                    <XCircle className="h-5 w-5 text-red-500" />
                  ) : validation && validation.warning_count > 0 ? (
                    <AlertTriangle className="h-5 w-5 text-yellow-500" />
                  ) : (
                    <CheckCircle2 className="h-5 w-5 text-muted-foreground" />
                  )}
                  Validation
                </CardTitle>
                <CardDescription>
                  {validateProject.isPending
                    ? 'Running validation checks...'
                    : validation?.valid
                    ? 'All checks passed'
                    : validation
                    ? `${validation.error_count} errors, ${validation.warning_count} warnings`
                    : 'Click refresh to validate'}
                </CardDescription>
              </div>
              {validation && (
                <div className="flex items-center gap-2">
                  {validation.error_count > 0 && (
                    <Badge variant="destructive">{validation.error_count} errors</Badge>
                  )}
                  {validation.warning_count > 0 && (
                    <Badge variant="secondary">{validation.warning_count} warnings</Badge>
                  )}
                  {validation.valid && (
                    <Badge variant="default" className="bg-green-500">Passed</Badge>
                  )}
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <ValidationPanel
              issues={validation?.issues || []}
              isLoading={validateProject.isPending}
            />
          </CardContent>
        </Card>

        {/* Export Preview */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Export Preview</CardTitle>
                <CardDescription>
                  Files that will be generated in .agents/ folder
                </CardDescription>
              </div>
              {preview && (
                <div className="text-sm text-muted-foreground">
                  {preview.total_files} files · {formatBytes(preview.total_size_bytes)}
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {isLoadingPreview ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : preview ? (
              <ExportTreeView tree={preview.tree} />
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                No preview available
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Export Actions */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <h3 className="font-medium">Download Export</h3>
              <p className="text-sm text-muted-foreground">
                {canExport
                  ? 'Export your project as a ZIP archive containing the .agents/ folder structure.'
                  : 'Fix validation errors before exporting.'}
              </p>
            </div>
            <Button
              size="lg"
              onClick={handleExport}
              disabled={!canExport || exportToZip.isPending}
            >
              {exportToZip.isPending ? (
                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              ) : (
                <Download className="mr-2 h-5 w-5" />
              )}
              Download ZIP
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
