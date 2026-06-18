import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { mapApi } from '../endpoints';
import { queryKeys } from '../../query-client';
import { FlowRelationshipType } from '../types';

/**
 * Hook to fetch map visualization data
 */
export function useMapVisualization(projectSlug: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.mapVisualization(projectSlug),
    queryFn: () => mapApi.getMapVisualization(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: 30 * 1000, // 30 seconds (map can change frequently during analysis)
  });
}

/**
 * Hook to refresh/recompute map relationships
 */
export function useRefreshMap(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => mapApi.refreshMap(projectSlug),
    onSuccess: () => {
      // Invalidate all map-related queries
      queryClient.invalidateQueries({ queryKey: queryKeys.mapVisualization(projectSlug) });
      queryClient.invalidateQueries({ queryKey: queryKeys.mapObjects(projectSlug) });
      queryClient.invalidateQueries({ queryKey: queryKeys.mapDependencies(projectSlug) });
      queryClient.invalidateQueries({ queryKey: queryKeys.mapClusters(projectSlug) });
    },
  });
}

/**
 * Hook to list discovered objects
 */
export function useMapObjects(projectSlug: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.mapObjects(projectSlug),
    queryFn: () => mapApi.listObjects(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: 1 * 60 * 1000, // 1 minute
  });
}

/**
 * Hook to get a single object with packages
 */
export function useMapObject(projectSlug: string, objectId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.mapObject(projectSlug, objectId),
    queryFn: () => mapApi.getObject(projectSlug, objectId),
    enabled: enabled && !!projectSlug && !!objectId,
    staleTime: 1 * 60 * 1000, // 1 minute
  });
}

/**
 * Hook to list flow dependencies
 */
export function useMapDependencies(projectSlug: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.mapDependencies(projectSlug),
    queryFn: () => mapApi.listDependencies(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: 1 * 60 * 1000, // 1 minute
  });
}

/**
 * Hook to create a manual dependency
 */
export function useCreateDependency(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      upstream_package_id: string;
      downstream_package_id: string;
      relationship_type?: FlowRelationshipType;
    }) => mapApi.createDependency(projectSlug, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.mapVisualization(projectSlug) });
      queryClient.invalidateQueries({ queryKey: queryKeys.mapDependencies(projectSlug) });
    },
  });
}

/**
 * Hook to confirm/reject a dependency
 */
export function useConfirmDependency(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ depId, data }: { depId: string; data: { confirmed: boolean; rejected?: boolean } }) =>
      mapApi.confirmDependency(projectSlug, depId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.mapVisualization(projectSlug) });
      queryClient.invalidateQueries({ queryKey: queryKeys.mapDependencies(projectSlug) });
    },
  });
}

/**
 * Hook to delete a dependency
 */
export function useDeleteDependency(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (depId: string) => mapApi.deleteDependency(projectSlug, depId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.mapVisualization(projectSlug) });
      queryClient.invalidateQueries({ queryKey: queryKeys.mapDependencies(projectSlug) });
    },
  });
}

/**
 * Hook to list clusters
 */
export function useMapClusters(projectSlug: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.mapClusters(projectSlug),
    queryFn: () => mapApi.listClusters(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: 1 * 60 * 1000, // 1 minute
  });
}

/**
 * Hook to get a single cluster with members
 */
export function useMapCluster(projectSlug: string, clusterId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.mapCluster(projectSlug, clusterId),
    queryFn: () => mapApi.getCluster(projectSlug, clusterId),
    enabled: enabled && !!projectSlug && !!clusterId,
    staleTime: 1 * 60 * 1000, // 1 minute
  });
}

/**
 * Hook to get wave suggestions
 */
export function useSuggestWaves(projectSlug: string) {
  return useMutation({
    mutationFn: () => mapApi.suggestWaves(projectSlug),
  });
}

/**
 * Hook to assign wave to a package
 */
export function useAssignWave(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ packageId, wave }: { packageId: string; wave: number }) =>
      mapApi.assignWave(projectSlug, packageId, wave),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.mapVisualization(projectSlug) });
      queryClient.invalidateQueries({ queryKey: queryKeys.mapClusters(projectSlug) });
    },
  });
}
