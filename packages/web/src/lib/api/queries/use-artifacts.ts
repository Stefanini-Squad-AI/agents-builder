import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { artifactApi, UploadArtifactRequest } from '../endpoints/artifacts';
import { queryKeys } from '../../query-client';
import { ArtifactSummary, ExtractionStatus } from '../types';

/**
 * Hook to list all artifacts for a project
 */
export function useProjectArtifacts(projectSlug: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.artifacts(projectSlug),
    queryFn: () => artifactApi.listProjectArtifacts(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: 30 * 1000, // 30 seconds
  });
}

/**
 * Hook to get a single artifact with optional polling for status updates
 * Automatically polls while status is 'pending' or 'extracting'
 */
export function useArtifact(artifactId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.artifact(artifactId),
    queryFn: () => artifactApi.getArtifact(artifactId),
    enabled: enabled && !!artifactId,
    staleTime: 5 * 1000, // 5 seconds
    refetchInterval: (query) => {
      const data = query.state.data as ArtifactSummary | undefined;
      if (!data) return false;
      // Poll every 2 seconds while extraction is in progress
      const isProcessing = [
        ExtractionStatus.PENDING,
        ExtractionStatus.EXTRACTING,
      ].includes(data.extraction_status);
      return isProcessing ? 2000 : false;
    },
  });
}

/**
 * Hook to poll multiple artifacts for status updates
 * Useful when uploading multiple files at once
 */
export function useArtifactsPolling(
  projectSlug: string,
  artifactIds: string[],
  enabled = true
) {
  const queryClient = useQueryClient();

  return useQuery({
    queryKey: [...queryKeys.artifacts(projectSlug), 'polling', artifactIds],
    queryFn: async () => {
      const results = await Promise.all(
        artifactIds.map((id) => artifactApi.getArtifact(id))
      );
      // Update individual artifact caches
      results.forEach((artifact) => {
        queryClient.setQueryData(queryKeys.artifact(artifact.id), artifact);
      });
      return results;
    },
    enabled: enabled && artifactIds.length > 0,
    refetchInterval: (query) => {
      const data = query.state.data as ArtifactSummary[] | undefined;
      if (!data) return false;
      // Poll while any artifact is still processing
      const anyProcessing = data.some((a) =>
        [ExtractionStatus.PENDING, ExtractionStatus.EXTRACTING].includes(
          a.extraction_status
        )
      );
      return anyProcessing ? 2000 : false;
    },
  });
}

/**
 * Hook to upload an artifact
 */
export function useUploadArtifact(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: UploadArtifactRequest) =>
      artifactApi.uploadArtifact(projectSlug, request),
    onSuccess: (newArtifact) => {
      // Add to artifacts list
      queryClient.setQueryData<ArtifactSummary[]>(
        queryKeys.artifacts(projectSlug),
        (old) => (old ? [newArtifact, ...old] : [newArtifact])
      );
      // Set individual artifact cache
      queryClient.setQueryData(queryKeys.artifact(newArtifact.id), newArtifact);
    },
  });
}

/**
 * Hook to upload multiple artifacts
 */
export function useUploadMultipleArtifacts(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (
      files: Array<{ file: File; kind?: string; onProgress?: (p: number) => void }>
    ) => {
      const results: ArtifactSummary[] = [];
      for (const { file, kind, onProgress } of files) {
        const result = await artifactApi.uploadArtifact(projectSlug, {
          file,
          kind: kind as any,
          onProgress,
        });
        results.push(result);
      }
      return results;
    },
    onSuccess: (newArtifacts) => {
      // Add all to artifacts list
      queryClient.setQueryData<ArtifactSummary[]>(
        queryKeys.artifacts(projectSlug),
        (old) => (old ? [...newArtifacts, ...old] : newArtifacts)
      );
      // Set individual artifact caches
      newArtifacts.forEach((artifact) => {
        queryClient.setQueryData(queryKeys.artifact(artifact.id), artifact);
      });
    },
  });
}

/**
 * Hook to retry a failed artifact extraction
 */
export function useRetryArtifact(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (artifactId: string) => artifactApi.retryArtifact(artifactId),
    onSuccess: (updatedArtifact) => {
      // Update individual cache
      queryClient.setQueryData(
        queryKeys.artifact(updatedArtifact.id),
        updatedArtifact
      );
      // Invalidate list to refresh
      queryClient.invalidateQueries({
        queryKey: queryKeys.artifacts(projectSlug),
      });
    },
  });
}

/**
 * Hook to delete an artifact
 */
export function useDeleteArtifact(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (artifactId: string) => artifactApi.deleteArtifact(artifactId),
    onMutate: async (artifactId) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({
        queryKey: queryKeys.artifacts(projectSlug),
      });

      // Snapshot previous value
      const previousArtifacts = queryClient.getQueryData<ArtifactSummary[]>(
        queryKeys.artifacts(projectSlug)
      );

      // Optimistically remove from list
      if (previousArtifacts) {
        queryClient.setQueryData(
          queryKeys.artifacts(projectSlug),
          previousArtifacts.filter((a) => a.id !== artifactId)
        );
      }

      return { previousArtifacts };
    },
    onError: (error, artifactId, context) => {
      // Rollback on error
      if (context?.previousArtifacts) {
        queryClient.setQueryData(
          queryKeys.artifacts(projectSlug),
          context.previousArtifacts
        );
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.artifacts(projectSlug),
      });
    },
  });
}

/**
 * Get artifact stats for a project
 */
export function useArtifactStats(projectSlug: string, enabled = true) {
  const { data: artifacts } = useProjectArtifacts(projectSlug, enabled);

  if (!artifacts) {
    return {
      total: 0,
      pending: 0,
      extracting: 0,
      extracted: 0,
      failed: 0,
      totalSize: 0,
    };
  }

  return {
    total: artifacts.length,
    pending: artifacts.filter((a) => a.extraction_status === ExtractionStatus.PENDING).length,
    extracting: artifacts.filter((a) => a.extraction_status === ExtractionStatus.EXTRACTING).length,
    extracted: artifacts.filter((a) => a.extraction_status === ExtractionStatus.EXTRACTED).length,
    failed: artifacts.filter((a) => a.extraction_status === ExtractionStatus.FAILED).length,
    totalSize: artifacts.reduce((sum, a) => sum + a.size_bytes, 0),
  };
}
