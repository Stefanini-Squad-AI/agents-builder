import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { skillsApi } from '../endpoints';
import { queryKeys, invalidateProject } from '../../query-client';
import {
  SkillView,
  CreateSkillRequest,
  UpdateSkillRequest,
  BulkCreateSkillsRequest,
  ProposeSkillsResponse,
  SkillStatsResponse,
  DraftSkillBodyRequest,
  DraftAllSkillsRequest,
  CreateResourceRequest,
  UpdateResourceRequest,
} from '../types';

/**
 * Hook to fetch project skills
 * @param projectSlug - Project slug
 * @param enabled - Whether the query is enabled
 * @param refetchInterval - Polling interval in ms (0 = disabled)
 */
export function useProjectSkills(
  projectSlug: string,
  enabled = true,
  refetchInterval = 0
) {
  return useQuery({
    queryKey: queryKeys.skills(projectSlug),
    queryFn: () => skillsApi.listProjectSkills(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: refetchInterval > 0 ? 0 : 5 * 60 * 1000, // No stale time when polling
    refetchInterval: refetchInterval > 0 ? refetchInterval : false,
  });
}

/**
 * Hook to fetch a specific skill
 */
export function useSkill(projectSlug: string, skillSlug: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.skill(projectSlug, skillSlug),
    queryFn: () => skillsApi.getSkill(projectSlug, skillSlug),
    enabled: enabled && !!projectSlug && !!skillSlug,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to get skills statistics
 * @param projectSlug - Project slug
 * @param enabled - Whether the query is enabled
 * @param refetchInterval - Polling interval in ms (0 = disabled)
 */
export function useSkillStats(
  projectSlug: string,
  enabled = true,
  refetchInterval = 0
) {
  return useQuery({
    queryKey: [...queryKeys.skills(projectSlug), 'stats'],
    queryFn: () => skillsApi.getSkillStats(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: refetchInterval > 0 ? 0 : 2 * 60 * 1000, // No stale time when polling
    refetchInterval: refetchInterval > 0 ? refetchInterval : false,
  });
}

/**
 * Hook to create a new skill
 */
export function useCreateSkill(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: CreateSkillRequest) =>
      skillsApi.createSkill(projectSlug, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.skills(projectSlug) });
      invalidateProject(projectSlug);
    },
    onError: (error) => {
      console.error('Failed to create skill:', error);
    },
  });
}

/**
 * Hook to update skill content
 */
export function useUpdateSkill(projectSlug: string, skillSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: UpdateSkillRequest) =>
      skillsApi.updateSkill(projectSlug, skillSlug, request),
    onMutate: async (newData) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: queryKeys.skill(projectSlug, skillSlug) });

      // Snapshot previous value
      const previousSkill = queryClient.getQueryData<SkillView>(
        queryKeys.skill(projectSlug, skillSlug)
      );

      // Optimistically update
      if (previousSkill) {
        queryClient.setQueryData<SkillView>(queryKeys.skill(projectSlug, skillSlug), {
          ...previousSkill,
          ...newData,
        });
      }

      return { previousSkill };
    },
    onError: (error, _newData, context) => {
      // Rollback on error
      if (context?.previousSkill) {
        queryClient.setQueryData(
          queryKeys.skill(projectSlug, skillSlug),
          context.previousSkill
        );
      }
      console.error('Failed to update skill:', error);
    },
    onSettled: () => {
      // Always refetch after error or success
      queryClient.invalidateQueries({ queryKey: queryKeys.skill(projectSlug, skillSlug) });
      queryClient.invalidateQueries({ queryKey: queryKeys.skills(projectSlug) });
    },
  });
}

/**
 * Hook to delete a skill
 */
export function useDeleteSkill(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (skillSlug: string) => skillsApi.deleteSkill(projectSlug, skillSlug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.skills(projectSlug) });
      invalidateProject(projectSlug);
    },
    onError: (error) => {
      console.error('Failed to delete skill:', error);
    },
  });
}

/**
 * Hook to propose skills using LLM
 * This calls the AI to generate 5-10 skill suggestions based on project context
 */
export function useProposeSkills(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => skillsApi.proposeSkills(projectSlug),
    onSuccess: () => {
      // Invalidate any cached data that might be affected
      queryClient.invalidateQueries({ queryKey: queryKeys.skills(projectSlug) });
    },
    onError: (error) => {
      console.error('Failed to propose skills:', error);
    },
  });
}

/**
 * Hook to bulk create skills from proposals
 */
export function useBulkCreateSkills(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: BulkCreateSkillsRequest) =>
      skillsApi.bulkCreateSkills(projectSlug, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.skills(projectSlug) });
      invalidateProject(projectSlug);
    },
    onError: (error) => {
      console.error('Failed to bulk create skills:', error);
    },
  });
}

/**
 * Hook to draft/regenerate skill body using LLM
 */
export function useDraftSkillBody(projectSlug: string, skillSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: DraftSkillBodyRequest = {}) =>
      skillsApi.draftSkillBody(projectSlug, skillSlug, request),
    onSuccess: (data) => {
      // Optimistically update the skill with the new body
      const currentSkill = queryClient.getQueryData<SkillView>(
        queryKeys.skill(projectSlug, skillSlug)
      );
      if (currentSkill) {
        queryClient.setQueryData<SkillView>(queryKeys.skill(projectSlug, skillSlug), {
          ...currentSkill,
          body_md: data.body_md,
        });
      }
      // Invalidate to ensure consistency
      queryClient.invalidateQueries({ queryKey: queryKeys.skill(projectSlug, skillSlug) });
    },
    onError: (error) => {
      console.error('Failed to draft skill body:', error);
    },
  });
}

/**
 * Hook to draft all skills that need drafting (empty body_md)
 * Queues background jobs for each skill
 */
export function useDraftAllSkills(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: DraftAllSkillsRequest = {}) =>
      skillsApi.draftAllSkills(projectSlug, request),
    onSuccess: () => {
      // Invalidate skills list to reflect drafting status
      queryClient.invalidateQueries({ queryKey: queryKeys.skills(projectSlug) });
    },
    onError: (error) => {
      console.error('Failed to queue skill drafting:', error);
    },
  });
}

/**
 * Hook to list skill resources
 */
export function useSkillResources(projectSlug: string, skillSlug: string, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.skill(projectSlug, skillSlug), 'resources'],
    queryFn: () => skillsApi.listSkillResources(projectSlug, skillSlug),
    enabled: enabled && !!projectSlug && !!skillSlug,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to create a skill resource
 */
export function useCreateSkillResource(projectSlug: string, skillSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: CreateResourceRequest) =>
      skillsApi.createSkillResource(projectSlug, skillSlug, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.skill(projectSlug, skillSlug) });
    },
    onError: (error) => {
      console.error('Failed to create skill resource:', error);
    },
  });
}

/**
 * Hook to update a skill resource
 */
export function useUpdateSkillResource(projectSlug: string, skillSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ resourceId, request }: { resourceId: string; request: UpdateResourceRequest }) =>
      skillsApi.updateSkillResource(projectSlug, skillSlug, resourceId, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.skill(projectSlug, skillSlug) });
    },
    onError: (error) => {
      console.error('Failed to update skill resource:', error);
    },
  });
}

/**
 * Hook to delete a skill resource
 */
export function useDeleteSkillResource(projectSlug: string, skillSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (resourceId: string) =>
      skillsApi.deleteSkillResource(projectSlug, skillSlug, resourceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.skill(projectSlug, skillSlug) });
    },
    onError: (error) => {
      console.error('Failed to delete skill resource:', error);
    },
  });
}

// Legacy aliases for backward compatibility
/** @deprecated Use useProjectSkills */
export const useSkills = useProjectSkills;

/** @deprecated Use useSkillStats */
export const useSkillsStats = useSkillStats;

/** @deprecated Use useProposeSkills */
export const useProposeSkillset = useProposeSkills;