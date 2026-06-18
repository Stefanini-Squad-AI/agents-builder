import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { qaApi } from '../endpoints';
import { queryKeys, invalidateProject } from '../../query-client';
import { QaAnswerView, SetQaAnswerRequest } from '../types';

/**
 * Hook to fetch project Q&A answers
 */
export function useQaAnswers(projectSlug: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.qa(projectSlug),
    queryFn: () => qaApi.getQaAnswers(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}

/**
 * Hook to fetch specific Q&A answer
 */
export function useQaAnswer(projectSlug: string, questionKey: string, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.qa(projectSlug), questionKey],
    queryFn: () => qaApi.getQaAnswer(projectSlug, questionKey),
    enabled: enabled && !!projectSlug && !!questionKey,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}

/**
 * Hook to get Q&A statistics
 */
export function useQaStats(projectSlug: string, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.qa(projectSlug), 'stats'],
    queryFn: () => qaApi.getQaStats(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: 1 * 60 * 1000, // 1 minute
  });
}

/**
 * Hook to get Q&A summary
 */
export function useQaSummary(projectSlug: string, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.qa(projectSlug), 'summary'],
    queryFn: () => qaApi.getQaSummary(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: 1 * 60 * 1000, // 1 minute
  });
}

/**
 * Hook to get standard questions catalog
 */
export function useStandardQuestions() {
  return useQuery({
    queryKey: ['qa', 'standard-questions'],
    queryFn: () => qaApi.getStandardQuestions(),
    staleTime: 10 * 60 * 1000, // 10 minutes (rarely changes)
  });
}

/**
 * Hook to check project readiness
 */
export function useProjectReadiness(projectSlug: string, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.qa(projectSlug), 'readiness'],
    queryFn: () => qaApi.checkProjectReadiness(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: 30 * 1000, // 30 seconds
  });
}

/**
 * Hook to set Q&A answer
 */
export function useSetQaAnswer(projectSlug: string, questionKey: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: SetQaAnswerRequest) => qaApi.setQaAnswer(projectSlug, questionKey, data),
    onMutate: async (newData) => {
      // Cancel outgoing refetches for Q&A
      await queryClient.cancelQueries({ queryKey: queryKeys.qa(projectSlug) });
      await queryClient.cancelQueries({ queryKey: [...queryKeys.qa(projectSlug), questionKey] });

      // Snapshot previous values
      const previousAnswers = queryClient.getQueryData<QaAnswerView[]>(queryKeys.qa(projectSlug));
      const previousAnswer = queryClient.getQueryData<QaAnswerView>([...queryKeys.qa(projectSlug), questionKey]);

      // Optimistically update the specific answer
      if (previousAnswer) {
        const updatedAnswer: QaAnswerView = {
          ...previousAnswer,
          answer_md: newData.answer_md,
          updated_at: new Date().toISOString(),
          is_answered: Boolean(newData.answer_md && newData.answer_md.trim()),
        };
        queryClient.setQueryData([...queryKeys.qa(projectSlug), questionKey], updatedAnswer);
      }

      // Optimistically update the answers list
      if (previousAnswers) {
        const updatedAnswers = previousAnswers.map(answer => 
          answer.question_key === questionKey 
            ? { 
                ...answer, 
                answer_md: newData.answer_md, 
                updated_at: new Date().toISOString(),
                is_answered: Boolean(newData.answer_md && newData.answer_md.trim()),
              }
            : answer
        );
        
        queryClient.setQueryData(queryKeys.qa(projectSlug), updatedAnswers);
      }

      return { previousAnswers, previousAnswer };
    },
    onError: (error, newData, context) => {
      // Rollback on error
      if (context?.previousAnswers) {
        queryClient.setQueryData(queryKeys.qa(projectSlug), context.previousAnswers);
      }
      if (context?.previousAnswer) {
        queryClient.setQueryData([...queryKeys.qa(projectSlug), questionKey], context.previousAnswer);
      }
      console.error('Failed to set Q&A answer:', error);
    },
    onSettled: () => {
      // Always refetch after error or success
      queryClient.invalidateQueries({ queryKey: queryKeys.qa(projectSlug) });
      queryClient.invalidateQueries({ queryKey: [...queryKeys.qa(projectSlug), questionKey] });
      
      // Also invalidate stats and readiness
      queryClient.invalidateQueries({ queryKey: [...queryKeys.qa(projectSlug), 'stats'] });
      queryClient.invalidateQueries({ queryKey: [...queryKeys.qa(projectSlug), 'readiness'] });
    },
  });
}

/**
 * Hook to bulk set multiple Q&A answers
 */
export function useBulkSetQaAnswers(projectSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (answers: Array<{ questionKey: string; answer_md: string }>) => {
      const results = [];
      for (const { questionKey, answer_md } of answers) {
        const result = await qaApi.setQaAnswer(projectSlug, questionKey, { answer_md });
        results.push(result);
      }
      return results;
    },
    onSuccess: () => {
      // Invalidate all Q&A related queries
      queryClient.invalidateQueries({ queryKey: queryKeys.qa(projectSlug) });
      queryClient.invalidateQueries({ queryKey: queryKeys.projectContext(projectSlug) });
    },
    onError: (error) => {
      console.error('Failed to bulk set Q&A answers:', error);
    },
  });
}