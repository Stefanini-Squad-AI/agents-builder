import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { exportApi } from '../endpoints';
import { queryKeys } from '../../query-client';
import { ExportView, ExportKind, ValidationResponse, ExportPreviewResponse } from '../types';

/**
 * Hook to validate project before export
 */
export function useValidateProject(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => exportApi.validateProject(projectSlug),
    onSuccess: (data) => {
      // Cache the validation result
      queryClient.setQueryData([...queryKeys.exports(projectSlug), 'validation'], data);
    },
    onError: (error) => {
      console.error('Failed to validate project:', error);
    },
  });
}

/**
 * Hook to get export preview (tree structure)
 */
export function useExportPreview(projectSlug: string, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.exports(projectSlug), 'preview'],
    queryFn: () => exportApi.getExportPreview(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: 30 * 1000, // 30 seconds (preview should be fresh)
  });
}

/**
 * Hook to export project as ZIP (download)
 */
export function useExportToZip(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => exportApi.exportToZip(projectSlug),
    onSuccess: () => {
      // Invalidate exports list
      queryClient.invalidateQueries({ queryKey: queryKeys.exports(projectSlug) });
    },
    onError: (error) => {
      console.error('Failed to export to ZIP:', error);
    },
  });
}

/**
 * Hook to fetch project exports
 */
export function useExports(projectSlug: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.exports(projectSlug),
    queryFn: () => exportApi.getExports(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}

/**
 * Hook to fetch specific export
 */
export function useExport(projectSlug: string, exportId: string, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.exports(projectSlug), exportId],
    queryFn: () => exportApi.getExport(projectSlug, exportId),
    enabled: enabled && !!projectSlug && !!exportId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to export project to filesystem
 */
export function useExportToFilesystem(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (targetPath?: string) => exportApi.exportToFilesystem(projectSlug, targetPath),
    onSuccess: () => {
      // Invalidate exports list to show new export
      queryClient.invalidateQueries({ queryKey: queryKeys.exports(projectSlug) });
    },
    onError: (error) => {
      console.error('Failed to export to filesystem:', error);
    },
  });
}

/**
 * Hook to export project as Jira CSV
 */
export function useExportToJiraCsv(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => exportApi.exportToJiraCsv(projectSlug),
    onSuccess: () => {
      // Invalidate exports list
      queryClient.invalidateQueries({ queryKey: queryKeys.exports(projectSlug) });
    },
    onError: (error) => {
      console.error('Failed to export to Jira CSV:', error);
    },
  });
}

/**
 * Hook to delete export
 */
export function useDeleteExport(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (exportId: string) => exportApi.deleteExport(projectSlug, exportId),
    onMutate: async (exportId) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: queryKeys.exports(projectSlug) });

      // Snapshot previous value
      const previousExports = queryClient.getQueryData<ExportView[]>(queryKeys.exports(projectSlug));

      // Optimistically remove
      if (previousExports) {
        const updatedExports = previousExports.filter(exp => exp.id !== exportId);
        queryClient.setQueryData(queryKeys.exports(projectSlug), updatedExports);
      }

      return { previousExports };
    },
    onError: (error, exportId, context) => {
      // Rollback on error
      if (context?.previousExports) {
        queryClient.setQueryData(queryKeys.exports(projectSlug), context.previousExports);
      }
      console.error('Failed to delete export:', error);
    },
    onSettled: () => {
      // Always refetch after error or success
      queryClient.invalidateQueries({ queryKey: queryKeys.exports(projectSlug) });
    },
  });
}