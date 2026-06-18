'use client';

import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { useProjectArtifacts, useUploadArtifact, useRetryArtifact } from '@/lib/api/queries/use-artifacts';
import { ArtifactSummary, ArtifactKind, ExtractionStatus } from '@/lib/api/types';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { 
  Upload, 
  FileText, 
  FileCode, 
  Loader2, 
  CheckCircle2, 
  XCircle, 
  RefreshCw,
  Trash2,
  ChevronRight,
  AlertCircle
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface ArtifactsStepProps {
  projectSlug: string;
  onNext: () => void;
}

const KIND_LABELS: Record<string, string> = {
  doc: 'Document',
  code: 'Code',
  spec: 'Specification',
  glossary: 'Glossary',
  other: 'Other',
};

const STATUS_CONFIG: Record<string, { icon: typeof Loader2; label: string; color: string }> = {
  pending: { icon: Loader2, label: 'Pending', color: 'text-yellow-500' },
  extracting: { icon: Loader2, label: 'Extracting...', color: 'text-blue-500' },
  extracted: { icon: CheckCircle2, label: 'Done', color: 'text-green-500' },
  failed: { icon: XCircle, label: 'Failed', color: 'text-red-500' },
};

function getFileIcon(kind: ArtifactKind) {
  switch (kind) {
    case ArtifactKind.CODE:
      return FileCode;
    default:
      return FileText;
  }
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

export function ArtifactsStep({ projectSlug, onNext }: ArtifactsStepProps) {
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});
  const [retryingArtifactId, setRetryingArtifactId] = useState<string | null>(null);
  
  const { data: artifacts, isLoading } = useProjectArtifacts(projectSlug);
  const uploadArtifact = useUploadArtifact(projectSlug);
  const retryArtifact = useRetryArtifact(projectSlug);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    for (const file of acceptedFiles) {
      const fileId = `${file.name}-${Date.now()}`;
      setUploadProgress(prev => ({ ...prev, [fileId]: 0 }));
      
      try {
        // Determine kind based on file extension
        let kind: ArtifactKind = ArtifactKind.DOC;
        const ext = file.name.split('.').pop()?.toLowerCase();
        if (['js', 'ts', 'tsx', 'jsx', 'py', 'java', 'go', 'rs', 'cs', 'cpp', 'c', 'h', 'rb', 'php', 'swift', 'kt'].includes(ext || '')) {
          kind = ArtifactKind.CODE;
        } else if (['yaml', 'yml', 'json'].includes(ext || '')) {
          kind = ArtifactKind.SPEC;
        }
        
        await uploadArtifact.mutateAsync({
          file,
          kind,
          onProgress: (progress) => {
            setUploadProgress(prev => ({ ...prev, [fileId]: progress }));
          },
        });
      } catch (error) {
        console.error('Upload failed:', error);
      } finally {
        setUploadProgress(prev => {
          const { [fileId]: removed, ...rest } = prev;
          return rest;
        });
      }
    }
  }, [uploadArtifact]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt', '.md'],
      'text/markdown': ['.md'],
      'application/json': ['.json'],
      'text/yaml': ['.yaml', '.yml'],
      'text/javascript': ['.js', '.jsx', '.ts', '.tsx'],
      'text/x-python': ['.py'],
      'text/x-java': ['.java'],
      'text/x-go': ['.go'],
      'text/x-rust': ['.rs'],
      'text/x-csharp': ['.cs'],
      'text/x-c': ['.c', '.cpp', '.h'],
      'application/xml': ['.xml', '.dtsx'],  // SSIS packages
      'text/xml': ['.xml', '.dtsx'],
    },
    maxSize: 50 * 1024 * 1024, // 50MB
  });

  const pendingCount = artifacts?.filter(a => 
    [ExtractionStatus.PENDING, ExtractionStatus.EXTRACTING].includes(a.extraction_status)
  ).length || 0;

  const uploadingCount = Object.keys(uploadProgress).length;

  return (
    <div className="space-y-6">
      {/* Description */}
      <p className="text-muted-foreground">
        Upload documents, specifications, and code files that provide context for your project.
        These will be extracted to markdown and used to inform AI suggestions.
      </p>

      {/* Drop Zone */}
      <div
        {...getRootProps()}
        className={cn(
          'border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors',
          isDragActive ? 'border-primary bg-primary/5' : 'border-muted-foreground/25 hover:border-primary/50'
        )}
      >
        <input {...getInputProps()} />
        <Upload className="h-10 w-10 mx-auto mb-4 text-muted-foreground" />
        {isDragActive ? (
          <p className="text-primary font-medium">Drop files here...</p>
        ) : (
          <>
            <p className="font-medium mb-1">Drag & drop files here</p>
            <p className="text-sm text-muted-foreground">
              or click to browse (PDF, DOCX, MD, code files up to 50MB)
            </p>
          </>
        )}
      </div>

      {/* Upload Progress */}
      {uploadingCount > 0 && (
        <div className="space-y-2">
          {Object.entries(uploadProgress).map(([fileId, progress]) => (
            <div key={fileId} className="flex items-center gap-3">
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
              <div className="flex-1">
                <div className="text-sm font-medium truncate">{fileId.split('-')[0]}</div>
                <Progress value={progress} className="h-1" />
              </div>
              <span className="text-sm text-muted-foreground">{progress}%</span>
            </div>
          ))}
        </div>
      )}

      {/* Artifacts List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : artifacts && artifacts.length > 0 ? (
        <div className="space-y-2">
          <h3 className="text-sm font-medium">
            Uploaded Files ({artifacts.length})
            {pendingCount > 0 && (
              <span className="ml-2 text-muted-foreground">
                • {pendingCount} extracting
              </span>
            )}
          </h3>
          <div className="border rounded-lg divide-y">
            {artifacts.map((artifact) => (
              <ArtifactRow
                key={artifact.id}
                artifact={artifact}
                onRetry={() => {
                  setRetryingArtifactId(artifact.id);
                  retryArtifact.mutate(artifact.id, {
                    onSettled: () => setRetryingArtifactId(null),
                  });
                }}
                isRetrying={retryingArtifactId === artifact.id}
              />
            ))}
          </div>
        </div>
      ) : (
        <div className="text-center py-8 text-muted-foreground">
          <AlertCircle className="h-8 w-8 mx-auto mb-2 opacity-50" />
          <p>No artifacts uploaded yet</p>
          <p className="text-sm">Upload files to provide context for AI suggestions</p>
        </div>
      )}

      {/* Navigation */}
      <div className="flex justify-between pt-4 border-t">
        <div className="text-sm text-muted-foreground">
          {artifacts?.length ? `${artifacts.length} file(s) uploaded` : 'Optional: Add context documents'}
        </div>
        <Button onClick={onNext}>
          Continue
          <ChevronRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

function ArtifactRow({ 
  artifact, 
  onRetry, 
  isRetrying 
}: { 
  artifact: ArtifactSummary; 
  onRetry: () => void; 
  isRetrying: boolean;
}) {
  const FileIcon = getFileIcon(artifact.kind);
  const statusConfig = STATUS_CONFIG[artifact.extraction_status] || STATUS_CONFIG.pending;
  const StatusIcon = statusConfig.icon;
  const isProcessing = [ExtractionStatus.PENDING, ExtractionStatus.EXTRACTING].includes(artifact.extraction_status);

  return (
    <div className="flex items-center gap-3 p-3">
      <FileIcon className="h-5 w-5 text-muted-foreground flex-shrink-0" />
      
      <div className="flex-1 min-w-0">
        <div className="font-medium truncate">{artifact.filename}</div>
        <div className="text-xs text-muted-foreground flex items-center gap-2">
          <span>{formatBytes(artifact.size_bytes)}</span>
          <span>•</span>
          <Badge variant="secondary" className="text-xs">
            {KIND_LABELS[artifact.kind] || artifact.kind}
          </Badge>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <div className={cn('flex items-center gap-1 text-sm', statusConfig.color)}>
          <StatusIcon className={cn('h-4 w-4', isProcessing && 'animate-spin')} />
          <span className="hidden sm:inline">{statusConfig.label}</span>
        </div>

        {artifact.extraction_status === ExtractionStatus.FAILED && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onRetry}
            disabled={isRetrying}
          >
            <RefreshCw className={cn('h-4 w-4', isRetrying && 'animate-spin')} />
          </Button>
        )}
      </div>
    </div>
  );
}
