'use client';

import { useCallback } from 'react';
import { useDropzone, FileRejection, Accept } from 'react-dropzone';
import { Upload, FileText, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

// Supported file types based on SPEC extractors
const ACCEPTED_FILE_TYPES: Accept = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/markdown': ['.md', '.markdown'],
  'text/plain': ['.txt'],
  'text/csv': ['.csv'],
  // Code files
  'text/x-python': ['.py'],
  'text/javascript': ['.js', '.jsx'],
  'text/typescript': ['.ts', '.tsx'],
  'application/json': ['.json'],
  'text/yaml': ['.yaml', '.yml'],
  'text/x-java-source': ['.java'],
  'text/x-csrc': ['.c', '.h'],
  'text/x-c++src': ['.cpp', '.hpp', '.cc'],
  'text/x-csharp': ['.cs'],
  'text/x-go': ['.go'],
  'text/x-rust': ['.rs'],
  'text/html': ['.html', '.htm'],
  'text/css': ['.css', '.scss', '.sass'],
  'application/sql': ['.sql'],
  'application/xml': ['.xml'],
};

// 50MB max file size (matching backend)
const MAX_FILE_SIZE = 50 * 1024 * 1024;

interface FileDropzoneProps {
  onFilesSelected: (files: File[]) => void;
  onError?: (message: string) => void;
  disabled?: boolean;
  maxFiles?: number;
  className?: string;
}

/**
 * File dropzone component for drag-and-drop file uploads.
 * Supports multiple file selection with validation.
 */
export function FileDropzone({
  onFilesSelected,
  onError,
  disabled = false,
  maxFiles = 10,
  className,
}: FileDropzoneProps) {
  const onDrop = useCallback(
    (acceptedFiles: File[], rejectedFiles: FileRejection[]) => {
      // Handle rejected files
      if (rejectedFiles.length > 0) {
        const errors = rejectedFiles.map((rejection) => {
          const fileName = rejection.file.name;
          const error = rejection.errors[0];
          
          if (error.code === 'file-too-large') {
            return `${fileName}: File too large (max 50MB)`;
          }
          if (error.code === 'file-invalid-type') {
            return `${fileName}: Unsupported file type`;
          }
          if (error.code === 'too-many-files') {
            return `Too many files (max ${maxFiles})`;
          }
          return `${fileName}: ${error.message}`;
        });

        onError?.(errors.join('\n'));
      }

      // Handle accepted files
      if (acceptedFiles.length > 0) {
        onFilesSelected(acceptedFiles);
      }
    },
    [onFilesSelected, onError, maxFiles]
  );

  const {
    getRootProps,
    getInputProps,
    isDragActive,
    isDragAccept,
    isDragReject,
  } = useDropzone({
    onDrop,
    accept: ACCEPTED_FILE_TYPES,
    maxSize: MAX_FILE_SIZE,
    maxFiles,
    disabled,
    multiple: true,
  });

  return (
    <div
      {...getRootProps()}
      className={cn(
        'relative flex flex-col items-center justify-center w-full min-h-[200px]',
        'border-2 border-dashed rounded-lg transition-all cursor-pointer',
        'hover:border-primary/50 hover:bg-accent/30',
        isDragActive && 'border-primary bg-accent/50',
        isDragAccept && 'border-green-500 bg-green-50 dark:bg-green-950',
        isDragReject && 'border-red-500 bg-red-50 dark:bg-red-950',
        disabled && 'opacity-50 cursor-not-allowed',
        !isDragActive && 'border-border bg-muted/30',
        className
      )}
    >
      <input {...getInputProps()} />

      <div className="flex flex-col items-center gap-4 p-8 text-center">
        {isDragReject ? (
          <>
            <AlertCircle className="h-12 w-12 text-red-500" />
            <div>
              <p className="text-lg font-medium text-red-600">
                Unsupported file type
              </p>
              <p className="text-sm text-muted-foreground">
                Drop PDF, DOCX, MD, TXT, CSV, or code files
              </p>
            </div>
          </>
        ) : isDragActive ? (
          <>
            <Upload className="h-12 w-12 text-primary animate-bounce" />
            <p className="text-lg font-medium text-primary">
              Drop files here...
            </p>
          </>
        ) : (
          <>
            <div className="p-4 rounded-full bg-primary/10">
              <FileText className="h-10 w-10 text-primary" />
            </div>
            <div>
              <p className="text-lg font-medium">
                Drag & drop files here, or click to browse
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                PDF, DOCX, Markdown, TXT, CSV, and code files up to 50MB
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default FileDropzone;
