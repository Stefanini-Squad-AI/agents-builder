'use client';

import { useState } from 'react';
import { 
  FileText, 
  FileCode, 
  FileSpreadsheet, 
  File,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  RotateCw,
  Trash2,
  Eye,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { cn } from '@/lib/utils';
import { ArtifactSummary, ExtractionStatus, ArtifactKind } from '@/lib/api/types';

interface ArtifactListProps {
  artifacts: ArtifactSummary[];
  onPreview?: (artifact: ArtifactSummary) => void;
  onRetry?: (artifactId: string) => void;
  onDelete?: (artifactId: string) => void;
  retryingArtifactId?: string | null;
  deletingArtifactId?: string | null;
}

// Format file size
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

// Get file icon based on kind
function getFileIcon(kind: ArtifactKind, filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase();
  
  // Code files
  if (kind === ArtifactKind.CODE || 
      ['py', 'js', 'ts', 'jsx', 'tsx', 'java', 'c', 'cpp', 'cs', 'go', 'rs', 'html', 'css'].includes(ext || '')) {
    return FileCode;
  }
  
  // Spreadsheet/data files
  if (ext === 'csv' || ext === 'xlsx') {
    return FileSpreadsheet;
  }
  
  // Document files
  if (['pdf', 'docx', 'doc', 'md', 'txt'].includes(ext || '')) {
    return FileText;
  }
  
  return File;
}

// Status badge component
function StatusBadge({ status }: { status: ExtractionStatus }) {
  switch (status) {
    case ExtractionStatus.PENDING:
      return (
        <Badge variant="secondary" className="gap-1">
          <Clock className="h-3 w-3" />
          Pending
        </Badge>
      );
    case ExtractionStatus.EXTRACTING:
      return (
        <Badge variant="secondary" className="gap-1 bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300">
          <Loader2 className="h-3 w-3 animate-spin" />
          Extracting
        </Badge>
      );
    case ExtractionStatus.EXTRACTED:
      return (
        <Badge variant="secondary" className="gap-1 bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
          <CheckCircle2 className="h-3 w-3" />
          Extracted
        </Badge>
      );
    case ExtractionStatus.FAILED:
      return (
        <Badge variant="destructive" className="gap-1">
          <XCircle className="h-3 w-3" />
          Failed
        </Badge>
      );
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

/**
 * Artifact list component displaying uploaded files with status and actions.
 */
export function ArtifactList({
  artifacts,
  onPreview,
  onRetry,
  onDelete,
  retryingArtifactId,
  deletingArtifactId,
}: ArtifactListProps) {
  const [deleteId, setDeleteId] = useState<string | null>(null);

  if (artifacts.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <FileText className="h-12 w-12 mx-auto mb-4 opacity-40" />
        <p>No artifacts uploaded yet</p>
        <p className="text-sm">Upload documents to provide context for your project</p>
      </div>
    );
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[40%]">File</TableHead>
            <TableHead>Size</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {artifacts.map((artifact) => {
            const FileIcon = getFileIcon(artifact.kind, artifact.filename);
            const canPreview = 
              artifact.extraction_status === ExtractionStatus.EXTRACTED &&
              artifact.content_md_excerpt;
            const canRetry = artifact.extraction_status === ExtractionStatus.FAILED;

            return (
              <TableRow key={artifact.id}>
                <TableCell>
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-muted">
                      <FileIcon className="h-5 w-5 text-muted-foreground" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium truncate">{artifact.filename}</p>
                      <p className="text-xs text-muted-foreground capitalize">
                        {artifact.kind}
                        {artifact.content_md_truncated && (
                          <span className="ml-2 text-amber-600">(truncated)</span>
                        )}
                      </p>
                    </div>
                  </div>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {formatBytes(artifact.size_bytes)}
                </TableCell>
                <TableCell>
                  <StatusBadge status={artifact.extraction_status} />
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex items-center justify-end gap-1">
                    {canPreview && onPreview && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onPreview(artifact)}
                        title="Preview content"
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                    )}
                    
                    {canRetry && onRetry && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onRetry(artifact.id)}
                        disabled={retryingArtifactId === artifact.id}
                        title="Retry extraction"
                      >
                        {retryingArtifactId === artifact.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <RotateCw className="h-4 w-4" />
                        )}
                      </Button>
                    )}
                    
                    {onDelete && (
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="text-destructive hover:text-destructive"
                            title="Delete artifact"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Delete artifact?</AlertDialogTitle>
                            <AlertDialogDescription>
                              This will permanently delete &quot;{artifact.filename}&quot;.
                              This action cannot be undone.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => onDelete(artifact.id)}
                              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                            >
                              {deletingArtifactId === artifact.id ? (
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                              ) : null}
                              Delete
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

export default ArtifactList;
