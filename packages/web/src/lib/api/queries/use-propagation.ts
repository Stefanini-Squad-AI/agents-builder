import { useMutation, useQueryClient } from '@tanstack/react-query';
import { propagationApi } from '../endpoints';
import { queryKeys } from '../../query-client';
import { PropagationScope } from '../types';

/**
 * Hook to preview what packages would be affected by propagation
 */
export function usePreviewPropagation(projectSlug: string) {
  return useMutation({
    mutationFn: (params: {
      decisionId: string;
      scope?: PropagationScope;
      clusterId?: string;
      domain?: string;
    }) =>
      propagationApi.previewPropagation(
        projectSlug,
        params.decisionId,
        params.scope,
        params.clusterId,
        params.domain
      ),
  });
}

/**
 * Hook to propagate a decision to matching packages
 */
export function usePropagatDecision(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: {
      decisionId: string;
      scope?: PropagationScope;
      clusterId?: string;
      domain?: string;
    }) =>
      propagationApi.propagateDecision(
        projectSlug,
        params.decisionId,
        params.scope,
        params.clusterId,
        params.domain
      ),
    onSuccess: () => {
      // Invalidate map visualization since package blockers may have changed
      queryClient.invalidateQueries({ queryKey: queryKeys.mapVisualization(projectSlug) });
    },
  });
}

/**
 * Hook to batch assign waves to packages
 */
export function useBatchAssignWaves(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (assignments: Array<{ package_id: string; wave: number }>) =>
      propagationApi.batchAssignWaves(projectSlug, assignments),
    onSuccess: () => {
      // Invalidate map visualization and clusters
      queryClient.invalidateQueries({ queryKey: queryKeys.mapVisualization(projectSlug) });
      queryClient.invalidateQueries({ queryKey: queryKeys.mapClusters(projectSlug) });
    },
  });
}
