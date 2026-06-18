import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { llmApi } from '../endpoints';
import { queryKeys } from '../../query-client';
import { LlmRunView } from '../types';

/**
 * Hook to fetch LLM runs for a project
 */
export function useLlmRuns(projectSlug: string, params?: {
  kind?: string;
  limit?: number;
  offset?: number;
}, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.llmRuns(projectSlug), params],
    queryFn: () => llmApi.getLlmRuns(projectSlug, params),
    enabled: enabled && !!projectSlug,
    staleTime: 1 * 60 * 1000, // 1 minute
  });
}

/**
 * Hook to fetch specific LLM run
 */
export function useLlmRun(runId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.llmRun(runId),
    queryFn: () => llmApi.getLlmRun(runId),
    enabled: enabled && !!runId,
    staleTime: 5 * 60 * 1000, // 5 minutes (runs don't change)
  });
}

/**
 * Hook to fetch LLM run details with full prompt/response
 */
export function useLlmRunDetails(runId: string, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.llmRun(runId), 'details'],
    queryFn: () => llmApi.getLlmRunDetails(runId),
    enabled: enabled && !!runId,
    staleTime: 10 * 60 * 1000, // 10 minutes (details don't change)
  });
}

/**
 * Hook to get LLM runs statistics
 */
export function useLlmRunsStats(projectSlug: string, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.llmRuns(projectSlug), 'stats'],
    queryFn: () => llmApi.getLlmRunsStats(projectSlug),
    enabled: enabled && !!projectSlug,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}

/**
 * Hook to get available LLM providers
 */
export function useLlmProviders() {
  return useQuery({
    queryKey: ['llm', 'providers'],
    queryFn: () => llmApi.getLlmProviders(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to get LLM provider configuration
 */
export function useLlmProviderConfig(provider: string, enabled = true) {
  return useQuery({
    queryKey: ['llm', 'providers', provider, 'config'],
    queryFn: () => llmApi.getLlmProviderConfig(provider),
    enabled: enabled && !!provider,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

/**
 * Hook to test LLM provider connectivity
 */
export function useTestLlmProvider() {
  return useMutation({
    mutationFn: ({ provider, model }: { provider: string; model?: string }) => 
      llmApi.testLlmProvider(provider, model),
    onError: (error) => {
      console.error('Failed to test LLM provider:', error);
    },
  });
}

/**
 * Hook to estimate LLM operation cost
 */
export function useEstimateLlmCost() {
  return useMutation({
    mutationFn: ({ provider, model, estimated_input_tokens, estimated_output_tokens }: {
      provider: string;
      model: string;
      estimated_input_tokens: number;
      estimated_output_tokens: number;
    }) => llmApi.estimateCost(provider, model, { estimated_input_tokens, estimated_output_tokens }),
    onError: (error) => {
      console.error('Failed to estimate LLM cost:', error);
    },
  });
}

/**
 * Hook to cancel running LLM operation
 */
export function useCancelLlmRun() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (runId: string) => llmApi.cancelLlmRun(runId),
    onSuccess: (_, runId) => {
      // Invalidate the specific run to refresh its status
      queryClient.invalidateQueries({ queryKey: queryKeys.llmRun(runId) });
    },
    onError: (error) => {
      console.error('Failed to cancel LLM run:', error);
    },
  });
}

/**
 * Hook to monitor LLM run status with polling
 */
export function useMonitorLlmRun(runId: string, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.llmRun(runId), 'monitor'],
    queryFn: () => llmApi.getLlmRun(runId),
    enabled: enabled && !!runId,
    refetchInterval: (query) => {
      // Poll every 2 seconds if run is in progress, otherwise stop polling
      return query.state.data?.status === 'in_progress' ? 2000 : false;
    },
    staleTime: 0, // Always consider stale for real-time monitoring
  });
}

/**
 * Hook to get recent LLM runs across all projects (for dashboard)
 */
export function useRecentLlmRuns(limit = 10) {
  return useQuery({
    queryKey: ['llm', 'recent-runs', limit],
    queryFn: () => llmApi.getLlmRuns('*', { limit }), // '*' for all projects
    staleTime: 1 * 60 * 1000, // 1 minute
  });
}

/**
 * Custom hook for streaming LLM operations
 */
export function useStreamLlmOperation() {
  return useMutation({
    mutationFn: ({ endpoint, data }: { endpoint: string; data: any }) => 
      llmApi.streamLlmOperation(endpoint, data),
    onError: (error) => {
      console.error('Failed to start streaming LLM operation:', error);
    },
  });
}

/**
 * Hook to get LLM run history for a specific operation type
 */
export function useLlmRunHistory(projectSlug: string, kind: string, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.llmRuns(projectSlug), 'history', kind],
    queryFn: () => llmApi.getLlmRuns(projectSlug, { kind, limit: 50 }),
    enabled: enabled && !!projectSlug && !!kind,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}