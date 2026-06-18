'use client';

import { useState, useCallback, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Loader2, AlertCircle, CheckCircle2, FileUp } from 'lucide-react';
import { FileDropzone } from './file-dropzone';
import { ArtifactList } from './artifact-list';
import { ArtifactPreview } from './artifact-preview';
import {
  useProjectArtifacts,
  useUploadArtifact,
  useRetryArtifact,
  useDeleteArtifact,
  useArtifactsPolling,
} from '@/lib/api/queries/use-artifacts';
import { ArtifactSummary, ExtractionStatus } from '@/lib/api/types';

interface UploadProgress {
  fileId: string;
  filename: string;
  progress: number;
  status: 'uploading' | 'processing' | 'complete' | 'error';
  error?: string;
}

interface ArtifactUploadProps {
  projectSlug: string;
  showTitle?: boolean;
}

/**
 * Main artifact upload component combining dropzone, progress, and list.
 */
export function ArtifactUpload({
  projectSlug,
  showTitle = true,
}: ArtifactUploadProps) {
  // State
  const [uploadProgress, setUploadProgress] = useState<UploadProgress[]>([]);
  const [previewArtifact, setPreviewArtifact] = useState<ArtifactSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryingArtifactId, setRetryingArtifactId] = useState<string | null>(null);
  const [deletingArtifactId, setDeletingArtifactId] = useState<string | null>(null);

  // Queries
  const { data: artifacts, isLoading: isLoadingArtifacts } = useProjectArtifacts(projectSlug);

  // Get IDs of artifacts that need polling
  const pollingIds = artifacts
    ?.filter((a) =>
      [ExtractionStatus.PENDING, ExtractionStatus.EXTRACTING].includes(a.extraction_status)
    )
    .map((a) => a.id) || [];

  // Poll for status updates
  useArtifactsPolling(projectSlug, pollingIds, pollingIds.length > 0);

  // Mutations
  const uploadMutation = useUploadArtifact(projectSlug);
  const retryMutation = useRetryArtifact(projectSlug);
  const deleteMutation = useDeleteArtifact(projectSlug);

  // Handle file selection from dropzone
  const handleFilesSelected = useCallback(
    async (files: File[]) => {
      setError(null);

      // Initialize progress for each file
      const newProgress: UploadProgress[] = files.map((file, index) => ({
        fileId: `upload-${Date.now()}-${index}`,
        filename: file.name,
        progress: 0,
        status: 'uploading',
      }));
      setUploadProgress((prev) => [...newProgress, ...prev]);

      // Upload files sequentially
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const fileId = newProgress[i].fileId;

        try {
          await uploadMutation.mutateAsync({
            file,
            onProgress: (progress) => {
              setUploadProgress((prev) =>
                prev.map((p) =>
                  p.fileId === fileId
                    ? { ...p, progress, status: progress < 100 ? 'uploading' : 'processing' }
                    : p
                )
              );
            },
          });

          // Mark as complete
          setUploadProgress((prev) =>
            prev.map((p) =>
              p.fileId === fileId ? { ...p, progress: 100, status: 'complete' } : p
            )
          );
        } catch (err) {
          // Mark as error
          setUploadProgress((prev) =>
            prev.map((p) =>
              p.fileId === fileId
                ? {
                    ...p,
                    status: 'error',
                    error: err instanceof Error ? err.message : 'Upload failed',
                  }
                : p
            )
          );
        }
      }

      // Clear completed uploads after a delay
      setTimeout(() => {
        setUploadProgress((prev) =>
          prev.filter((p) => p.status !== 'complete')
        );
      }, 3000);
    },
    [uploadMutation]
  );

  // Handle dropzone errors
  const handleDropzoneError = useCallback((message: string) => {
    setError(message);
  }, []);

  // Handle retry
  const handleRetry = useCallback(
    async (artifactId: string) => {
      setRetryingArtifactId(artifactId);
      try {
        await retryMutation.mutateAsync(artifactId);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Retry failed');
      } finally {
        setRetryingArtifactId(null);
      }
    },
    [retryMutation]
  );

  // Handle delete
  const handleDelete = useCallback(
    async (artifactId: string) => {
      setDeletingArtifactId(artifactId);
      try {
        await deleteMutation.mutateAsync(artifactId);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Delete failed');
      } finally {
        setDeletingArtifactId(null);
      }
    },
    [deleteMutation]
  );

  // Calculate stats
  const stats = {
    total: artifacts?.length || 0,
    processing: artifacts?.filter((a) =>
      [ExtractionStatus.PENDING, ExtractionStatus.EXTRACTING].includes(a.extraction_status)
    ).length || 0,
    extracted: artifacts?.filter((a) => a.extraction_status === ExtractionStatus.EXTRACTED).length || 0,
    failed: artifacts?.filter((a) => a.extraction_status === ExtractionStatus.FAILED).length || 0,
  };

  const isUploading = uploadProgress.some((p) => p.status === 'uploading');

  return (
    <div className="space-y-6">
      {showTitle && (
        <div>
          <h3 className="text-lg font-semibold">Project Artifacts</h3>
          <p className="text-muted-foreground">
            Upload documents, code samples, and other resources to provide context for your project.
          </p>
        </div>
      )}

      {/* Error alert */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription className="whitespace-pre-line">{error}</AlertDescription>
        </Alert>
      )}

      {/* Upload dropzone */}
      <FileDropzone
        onFilesSelected={handleFilesSelected}
        onError={handleDropzoneError}
        disabled={isUploading}
      />

      {/* Upload progress */}
      {uploadProgress.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <FileUp className="h-5 w-5" />
              Uploads
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {uploadProgress.map((item) => (
              <div key={item.fileId} className="space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-sm truncate max-w-[70%]">{item.filename}</span>
                  <div className="flex items-center gap-2">
                    {item.status === 'uploading' && (
                      <span className="text-xs text-muted-foreground">{item.progress}%</span>
                    )}
                    {item.status === 'processing' && (
                      <Badge variant="secondary" className="gap-1">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        Processing
                      </Badge>
                    )}
                    {item.status === 'complete' && (
                      <Badge className="gap-1 bg-green-100 text-green-700">
                        <CheckCircle2 className="h-3 w-3" />
                        Complete
                      </Badge>
                    )}
                    {item.status === 'error' && (
                      <Badge variant="destructive" className="gap-1">
                        <AlertCircle className="h-3 w-3" />
                        Error
                      </Badge>
                    )}
                  </div>
                </div>
                {item.status === 'uploading' && (
                  <Progress value={item.progress} className="h-1" />
                )}
                {item.status === 'error' && item.error && (
                  <p className="text-xs text-destructive">{item.error}</p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Stats summary */}
      {stats.total > 0 && (
        <div className="flex items-center gap-4 text-sm">
          <span className="text-muted-foreground">{stats.total} artifact{stats.total !== 1 ? 's' : ''}</span>
          {stats.processing > 0 && (
            <Badge variant="secondary" className="gap-1">
              <Loader2 className="h-3 w-3 animate-spin" />
              {stats.processing} processing
            </Badge>
          )}
          {stats.extracted > 0 && (
            <Badge className="gap-1 bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
              <CheckCircle2 className="h-3 w-3" />
              {stats.extracted} extracted
            </Badge>
          )}
          {stats.failed > 0 && (
            <Badge variant="destructive" className="gap-1">
              <AlertCircle className="h-3 w-3" />
              {stats.failed} failed
            </Badge>
          )}
        </div>
      )}

      {/* Artifact list */}
      {isLoadingArtifacts ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <ArtifactList
          artifacts={artifacts || []}
          onPreview={setPreviewArtifact}
          onRetry={handleRetry}
          onDelete={handleDelete}
          retryingArtifactId={retryingArtifactId}
          deletingArtifactId={deletingArtifactId}
        />
      )}

      {/* Preview modal */}
      <ArtifactPreview
        artifact={previewArtifact}
        open={!!previewArtifact}
        onOpenChange={(open) => !open && setPreviewArtifact(null)}
      />
    </div>
  );
}

export default ArtifactUpload;
