import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { gapsApi } from '../endpoints';
import { queryKeys } from '../../query-client';
import {
  GapStatus,
  CreateGapRequest,
  AddressBySkillRequest,
  CoverByMcpRequest,
  OutOfScopeRequest,
} from '../types';

/**
 * Helpers to invalidate the gap-related caches consistently after a mutation.
 */
function invalidateGapCaches(
  queryClient: ReturnType<typeof useQueryClient>,
  projectSlug: string
) {
  queryClient.invalidateQueries({
    queryKey: ['projects', projectSlug, 'gaps'],
  });
}

/** List gaps, optionally filtered by status. */
export function useProjectGaps(
  projectSlug: string,
  status?: GapStatus,
  enabled = true
) {
  return useQuery({
    queryKey: queryKeys.gaps(projectSlug, status),
    queryFn: () => gapsApi.listGaps(projectSlug, status),
    enabled: enabled && !!projectSlug,
    staleTime: 60 * 1000,
  });
}

/** Stats for the gaps panel header strip. */
export function useGapsStats(projectSlug: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.gapsStats(projectSlug),
    queryFn: () => gapsApi.getStats(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: 60 * 1000,
  });
}

/** Manually create a gap (source=manual). */
export function useCreateGap(projectSlug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateGapRequest) =>
      gapsApi.createGap(projectSlug, payload),
    onSuccess: () => {
      invalidateGapCaches(queryClient, projectSlug);
      toast.success('Gap created');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to create gap');
    },
  });
}

export function useAddressGapBySkill(projectSlug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      gapId,
      payload,
    }: {
      gapId: string;
      payload: AddressBySkillRequest;
    }) => gapsApi.addressBySkill(projectSlug, gapId, payload),
    onSuccess: () => {
      invalidateGapCaches(queryClient, projectSlug);
      toast.success('Gap addressed by skill');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to address gap');
    },
  });
}

export function useCoverGapByMcp(projectSlug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      gapId,
      payload,
    }: {
      gapId: string;
      payload: CoverByMcpRequest;
    }) => gapsApi.coverByMcp(projectSlug, gapId, payload),
    onSuccess: () => {
      invalidateGapCaches(queryClient, projectSlug);
      toast.success('Gap covered by MCP');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to cover gap');
    },
  });
}

export function useMarkGapOutOfScope(projectSlug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      gapId,
      payload,
    }: {
      gapId: string;
      payload: OutOfScopeRequest;
    }) => gapsApi.markOutOfScope(projectSlug, gapId, payload),
    onSuccess: () => {
      invalidateGapCaches(queryClient, projectSlug);
      toast.success('Gap marked as out of scope');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to mark gap out of scope');
    },
  });
}

export function useReopenGap(projectSlug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (gapId: string) => gapsApi.reopen(projectSlug, gapId),
    onSuccess: () => {
      invalidateGapCaches(queryClient, projectSlug);
      toast.success('Gap reopened');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to reopen gap');
    },
  });
}

export function useDeleteGap(projectSlug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (gapId: string) => gapsApi.deleteGap(projectSlug, gapId),
    onSuccess: () => {
      invalidateGapCaches(queryClient, projectSlug);
      toast.success('Gap deleted');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to delete gap');
    },
  });
}
