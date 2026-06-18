import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { cardsApi, phasesApi, backlogApi } from '../endpoints';
import { queryKeys, invalidateProject } from '../../query-client';
import { CardView, PhaseView, DraftCardRequest, Priority, CardStatus } from '../types';

/**
 * Hook to fetch project cards
 */
export function useCards(projectSlug: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.cards(projectSlug),
    queryFn: () => cardsApi.getCards(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to fetch a specific card
 */
export function useCard(projectSlug: string, cardId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.card(projectSlug, cardId),
    queryFn: () => cardsApi.getCard(projectSlug, cardId),
    enabled: enabled && !!projectSlug && !!cardId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to fetch project phases
 */
export function usePhases(projectSlug: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.phases(projectSlug),
    queryFn: () => phasesApi.getPhases(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to fetch a specific phase
 */
export function usePhase(projectSlug: string, phaseId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.phase(projectSlug, phaseId),
    queryFn: () => phasesApi.getPhase(projectSlug, phaseId),
    enabled: enabled && !!projectSlug && !!phaseId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to get cards statistics
 */
export function useCardsStats(projectSlug: string, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.cards(projectSlug), 'stats'],
    queryFn: () => cardsApi.getCardsStats(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}

/**
 * Hook to get project DAG
 */
export function useProjectDag(projectSlug: string, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.phases(projectSlug), 'dag'],
    queryFn: () => backlogApi.getProjectDag(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to propose backlog using AI
 */
export function useProposeBacklog(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => backlogApi.proposeBacklog(projectSlug),
    onSuccess: () => {
      // Invalidate all backlog-related data
      queryClient.invalidateQueries({ queryKey: queryKeys.phases(projectSlug) });
      queryClient.invalidateQueries({ queryKey: queryKeys.cards(projectSlug) });
      invalidateProject(projectSlug);
    },
    onError: (error) => {
      console.error('Failed to propose backlog:', error);
    },
  });
}

/**
 * Hook to draft a new card using AI
 */
export function useDraftCard(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: DraftCardRequest) => cardsApi.draftCard(projectSlug, data),
    onSuccess: () => {
      // Invalidate cards and phases
      queryClient.invalidateQueries({ queryKey: queryKeys.cards(projectSlug) });
      queryClient.invalidateQueries({ queryKey: queryKeys.phases(projectSlug) });
    },
    onError: (error) => {
      console.error('Failed to draft card:', error);
    },
  });
}

/**
 * Hook to update card content
 */
export function useUpdateCard(projectSlug: string, cardId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      title?: string;
      context_md?: string;
      task_md?: string;
      outputs_md?: string;
      acceptance_criteria_md?: string;
      human_gate?: boolean;
      human_gate_checklist_md?: string;
      story_points?: number;
      priority?: Priority;
      status?: CardStatus;
    }) => cardsApi.updateCard(projectSlug, cardId, data),
    onMutate: async (newData) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: queryKeys.card(projectSlug, cardId) });

      // Snapshot previous value
      const previousCard = queryClient.getQueryData<CardView>(queryKeys.card(projectSlug, cardId));

      // Optimistically update
      if (previousCard) {
        queryClient.setQueryData<CardView>(queryKeys.card(projectSlug, cardId), {
          ...previousCard,
          ...newData,
          updated_at: new Date().toISOString(),
        });
      }

      return { previousCard };
    },
    onError: (error, newData, context) => {
      // Rollback on error
      if (context?.previousCard) {
        queryClient.setQueryData(queryKeys.card(projectSlug, cardId), context.previousCard);
      }
      console.error('Failed to update card:', error);
    },
    onSettled: () => {
      // Always refetch after error or success
      queryClient.invalidateQueries({ queryKey: queryKeys.card(projectSlug, cardId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.cards(projectSlug) });
      queryClient.invalidateQueries({ queryKey: queryKeys.phases(projectSlug) });
    },
  });
}

/**
 * Hook to update card section
 */
export function useUpdateCardSection(projectSlug: string, cardId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ section, content }: { section: string; content: string }) => 
      cardsApi.updateCardSection(projectSlug, cardId, section, content),
    onMutate: async ({ section, content }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: queryKeys.card(projectSlug, cardId) });

      // Snapshot previous value
      const previousCard = queryClient.getQueryData<CardView>(queryKeys.card(projectSlug, cardId));

      // Optimistically update the specific section
      if (previousCard) {
        const updatedCard = { ...previousCard };
        (updatedCard as any)[`${section}_md`] = content;
        updatedCard.updated_at = new Date().toISOString();
        
        queryClient.setQueryData<CardView>(queryKeys.card(projectSlug, cardId), updatedCard);
      }

      return { previousCard };
    },
    onError: (error, variables, context) => {
      // Rollback on error
      if (context?.previousCard) {
        queryClient.setQueryData(queryKeys.card(projectSlug, cardId), context.previousCard);
      }
      console.error('Failed to update card section:', error);
    },
    onSettled: () => {
      // Always refetch after error or success
      queryClient.invalidateQueries({ queryKey: queryKeys.card(projectSlug, cardId) });
    },
  });
}

/**
 * Hook to render card as markdown
 */
export function useRenderCardMarkdown(projectSlug: string, cardId: string, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.card(projectSlug, cardId), 'render'],
    queryFn: () => cardsApi.renderCardMarkdown(projectSlug, cardId),
    enabled: enabled && !!projectSlug && !!cardId,
    staleTime: 1 * 60 * 1000, // 1 minute
  });
}

/**
 * Hook to update phase
 */
export function useUpdatePhase(projectSlug: string, phaseId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      name?: string;
      description_md?: string;
    }) => phasesApi.updatePhase(projectSlug, phaseId, data),
    onMutate: async (newData) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: queryKeys.phase(projectSlug, phaseId) });

      // Snapshot previous value
      const previousPhase = queryClient.getQueryData<PhaseView>(queryKeys.phase(projectSlug, phaseId));

      // Optimistically update
      if (previousPhase) {
        queryClient.setQueryData<PhaseView>(queryKeys.phase(projectSlug, phaseId), {
          ...previousPhase,
          ...newData,
        });
      }

      return { previousPhase };
    },
    onError: (error, newData, context) => {
      // Rollback on error
      if (context?.previousPhase) {
        queryClient.setQueryData(queryKeys.phase(projectSlug, phaseId), context.previousPhase);
      }
      console.error('Failed to update phase:', error);
    },
    onSettled: () => {
      // Always refetch after error or success
      queryClient.invalidateQueries({ queryKey: queryKeys.phase(projectSlug, phaseId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.phases(projectSlug) });
    },
  });
}

/**
 * Hook to validate backlog
 */
export function useValidateBacklog(projectSlug: string, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.phases(projectSlug), 'validate'],
    queryFn: () => backlogApi.validateBacklog(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: 30 * 1000, // 30 seconds
  });
}

/**
 * Hook to regenerate a specific card section using LLM
 */
export function useRegenerateCardSection(projectSlug: string, cardId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (section: string) => 
      cardsApi.regenerateCardSection(projectSlug, cardId, section),
    onSuccess: (data) => {
      // Update the specific section in the cache
      const previousCard = queryClient.getQueryData<CardView>(queryKeys.card(projectSlug, cardId));
      if (previousCard) {
        const updatedCard = { ...previousCard };
        (updatedCard as any)[`${data.section}_md`] = data.content;
        updatedCard.updated_at = new Date().toISOString();
        queryClient.setQueryData<CardView>(queryKeys.card(projectSlug, cardId), updatedCard);
      }
    },
    onSettled: () => {
      // Always refetch after error or success
      queryClient.invalidateQueries({ queryKey: queryKeys.card(projectSlug, cardId) });
    },
  });
}

/**
 * Hook to draft entire card content using LLM
 */
export function useDraftCardContent(projectSlug: string, cardId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => cardsApi.draftCardContent(projectSlug, cardId),
    onSuccess: (data) => {
      // Update the full card in the cache
      queryClient.setQueryData<CardView>(queryKeys.card(projectSlug, cardId), data.card);
    },
    onSettled: () => {
      // Always refetch after error or success
      queryClient.invalidateQueries({ queryKey: queryKeys.card(projectSlug, cardId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.cards(projectSlug) });
    },
  });
}

/**
 * Hook to update card dependencies
 */
export function useUpdateCardDependencies(projectSlug: string, cardId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { depends_on_codes: string[]; parallel_with_codes: string[] }) => 
      cardsApi.updateCardDependencies(projectSlug, cardId, data),
    onMutate: async (newData) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: queryKeys.card(projectSlug, cardId) });

      // Snapshot previous value
      const previousCard = queryClient.getQueryData<CardView>(queryKeys.card(projectSlug, cardId));

      // Optimistically update
      if (previousCard) {
        queryClient.setQueryData<CardView>(queryKeys.card(projectSlug, cardId), {
          ...previousCard,
          depends_on_codes: newData.depends_on_codes,
          parallel_with_codes: newData.parallel_with_codes,
          updated_at: new Date().toISOString(),
        });
      }

      return { previousCard };
    },
    onError: (error, newData, context) => {
      // Rollback on error
      if (context?.previousCard) {
        queryClient.setQueryData(queryKeys.card(projectSlug, cardId), context.previousCard);
      }
      console.error('Failed to update card dependencies:', error);
    },
    onSettled: () => {
      // Always refetch after error or success
      queryClient.invalidateQueries({ queryKey: queryKeys.card(projectSlug, cardId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.phases(projectSlug) });
    },
  });
}

/**
 * Hook to list card inputs
 */
export function useCardInputs(projectSlug: string, cardId: string, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.card(projectSlug, cardId), 'inputs'],
    queryFn: () => cardsApi.listCardInputs(projectSlug, cardId),
    enabled: enabled && !!projectSlug && !!cardId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to create card input
 */
export function useCreateCardInput(projectSlug: string, cardId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { kind: string; path: string; label?: string; order_no?: number }) => 
      cardsApi.createCardInput(projectSlug, cardId, data as any),
    onSuccess: () => {
      // Invalidate inputs list
      queryClient.invalidateQueries({ queryKey: [...queryKeys.card(projectSlug, cardId), 'inputs'] });
      queryClient.invalidateQueries({ queryKey: queryKeys.card(projectSlug, cardId) });
    },
    onError: (error) => {
      console.error('Failed to create card input:', error);
    },
  });
}

/**
 * Hook to update card input
 */
export function useUpdateCardInput(projectSlug: string, cardId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ inputId, data }: { inputId: string; data: { kind?: string; path?: string; label?: string; order_no?: number } }) => 
      cardsApi.updateCardInput(projectSlug, cardId, inputId, data as any),
    onSuccess: () => {
      // Invalidate inputs list
      queryClient.invalidateQueries({ queryKey: [...queryKeys.card(projectSlug, cardId), 'inputs'] });
      queryClient.invalidateQueries({ queryKey: queryKeys.card(projectSlug, cardId) });
    },
    onError: (error) => {
      console.error('Failed to update card input:', error);
    },
  });
}

/**
 * Hook to delete card input
 */
export function useDeleteCardInput(projectSlug: string, cardId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (inputId: string) => 
      cardsApi.deleteCardInput(projectSlug, cardId, inputId),
    onSuccess: () => {
      // Invalidate inputs list
      queryClient.invalidateQueries({ queryKey: [...queryKeys.card(projectSlug, cardId), 'inputs'] });
      queryClient.invalidateQueries({ queryKey: queryKeys.card(projectSlug, cardId) });
    },
    onError: (error) => {
      console.error('Failed to delete card input:', error);
    },
  });
}