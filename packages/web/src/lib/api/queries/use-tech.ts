import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { techApi, SetTechChoiceRequest, AddCustomItemRequest, DimensionWithChoices, TechStatsResponse } from '../endpoints/tech';
import { queryKeys } from '../../query-client';
import { TechChoiceView, TechChoiceRole } from '../types';

/**
 * Hook to fetch all tech dimensions (catalog)
 */
export function useTechDimensions() {
  return useQuery({
    queryKey: queryKeys.techDimensions,
    queryFn: () => techApi.getTechDimensions(),
    staleTime: 10 * 60 * 1000, // 10 minutes (rarely changes)
  });
}

/**
 * Hook to fetch specific tech dimension
 */
export function useTechDimension(dimensionSlug: string, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.techDimensions, dimensionSlug],
    queryFn: () => techApi.getTechDimension(dimensionSlug),
    enabled: enabled && !!dimensionSlug,
    staleTime: 10 * 60 * 1000,
  });
}

/**
 * Hook to fetch project tech choices
 */
export function useProjectTechChoices(projectSlug: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.techChoices(projectSlug),
    queryFn: () => techApi.getProjectTechChoices(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: 2 * 60 * 1000,
  });
}

/**
 * Hook to fetch all dimensions with project choices
 */
export function useDimensionsWithChoices(projectSlug: string, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.techChoices(projectSlug), 'dimensions'],
    queryFn: () => techApi.getDimensionsWithChoices(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: 2 * 60 * 1000,
  });
}

/**
 * Hook to fetch tech choices for specific dimension
 */
export function useDimensionChoices(projectSlug: string, dimensionSlug: string, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.techChoices(projectSlug), dimensionSlug],
    queryFn: () => techApi.getDimensionChoices(projectSlug, dimensionSlug),
    enabled: enabled && !!projectSlug && !!dimensionSlug,
    staleTime: 2 * 60 * 1000,
  });
}

/**
 * Hook to get tech statistics
 */
export function useTechStats(projectSlug: string, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.techChoices(projectSlug), 'stats'],
    queryFn: () => techApi.getTechStats(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: 1 * 60 * 1000,
  });
}

/**
 * Hook to get tech summary
 */
export function useTechSummary(projectSlug: string, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.techChoices(projectSlug), 'summary'],
    queryFn: () => techApi.getTechSummary(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: 1 * 60 * 1000,
  });
}

/**
 * Hook to set tech choice
 */
export function useSetTechChoice(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ 
      dimensionSlug, 
      itemSlug, 
      role, 
      notes 
    }: { 
      dimensionSlug: string; 
      itemSlug: string; 
      role: TechChoiceRole; 
      notes?: string;
    }) => techApi.setTechChoice(projectSlug, dimensionSlug, itemSlug, { role, notes }),
    onSuccess: () => {
      // Invalidate all tech-related queries
      queryClient.invalidateQueries({ queryKey: queryKeys.techChoices(projectSlug) });
      // Also invalidate dimensions with choices query explicitly
      queryClient.invalidateQueries({ queryKey: [...queryKeys.techChoices(projectSlug), 'dimensions'] });
      queryClient.invalidateQueries({ queryKey: [...queryKeys.techChoices(projectSlug), 'stats'] });
    },
  });
}

/**
 * Hook to remove tech choice
 */
export function useRemoveTechChoice(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ 
      dimensionSlug, 
      itemSlug 
    }: { 
      dimensionSlug: string; 
      itemSlug: string; 
    }) => techApi.removeTechChoice(projectSlug, dimensionSlug, itemSlug),
    onMutate: async ({ dimensionSlug, itemSlug }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.techChoices(projectSlug) });
      const previousChoices = queryClient.getQueryData<TechChoiceView[]>(queryKeys.techChoices(projectSlug));

      if (previousChoices) {
        const updatedChoices = previousChoices.filter(c => 
          !(c.dimension_slug === dimensionSlug && c.tech_item_slug === itemSlug)
        );
        queryClient.setQueryData(queryKeys.techChoices(projectSlug), updatedChoices);
      }

      return { previousChoices };
    },
    onError: (error, variables, context) => {
      if (context?.previousChoices) {
        queryClient.setQueryData(queryKeys.techChoices(projectSlug), context.previousChoices);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.techChoices(projectSlug) });
    },
  });
}

/**
 * Hook to mark dimension as TBD
 */
export function useMarkTbd(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ 
      dimensionSlug, 
      notes 
    }: { 
      dimensionSlug: string; 
      notes?: string; 
    }) => techApi.markTbd(projectSlug, dimensionSlug, { notes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.techChoices(projectSlug) });
    },
  });
}

/**
 * Hook to clear TBD marking
 */
export function useClearTbd(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (dimensionSlug: string) => techApi.clearTbd(projectSlug, dimensionSlug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.techChoices(projectSlug) });
    },
  });
}

/**
 * Hook to add custom tech item
 */
export function useAddCustomItem(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ 
      dimensionSlug, 
      ...data 
    }: { 
      dimensionSlug: string; 
    } & AddCustomItemRequest) => techApi.addCustomItem(projectSlug, dimensionSlug, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.techDimensions });
      queryClient.invalidateQueries({ queryKey: queryKeys.techChoices(projectSlug) });
    },
  });
}

/**
 * Hook to accept LLM suggestion
 */
export function useAcceptSuggestion(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ 
      dimensionSlug, 
      itemSlug 
    }: { 
      dimensionSlug: string; 
      itemSlug: string; 
    }) => techApi.acceptSuggestion(projectSlug, dimensionSlug, itemSlug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.techChoices(projectSlug) });
    },
  });
}

/**
 * Hook to dismiss LLM suggestion
 */
export function useDismissSuggestion(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ 
      dimensionSlug, 
      itemSlug 
    }: { 
      dimensionSlug: string; 
      itemSlug: string; 
    }) => techApi.dismissSuggestion(projectSlug, dimensionSlug, itemSlug),
    onMutate: async ({ dimensionSlug, itemSlug }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.techChoices(projectSlug) });
      const previousChoices = queryClient.getQueryData<TechChoiceView[]>(queryKeys.techChoices(projectSlug));

      if (previousChoices) {
        const updatedChoices = previousChoices.filter(c => 
          !(c.dimension_slug === dimensionSlug && c.tech_item_slug === itemSlug && !c.accepted)
        );
        queryClient.setQueryData(queryKeys.techChoices(projectSlug), updatedChoices);
      }

      return { previousChoices };
    },
    onError: (error, variables, context) => {
      if (context?.previousChoices) {
        queryClient.setQueryData(queryKeys.techChoices(projectSlug), context.previousChoices);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.techChoices(projectSlug) });
    },
  });
}