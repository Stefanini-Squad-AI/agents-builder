// System-level React Query hooks (health, worker status, etc.)

import { useQuery } from '@tanstack/react-query';
import { systemApi } from '../endpoints';
import type { WorkerStatusResponse } from '../types';

/**
 * Query key factory for system queries
 */
export const systemKeys = {
  all: ['system'] as const,
  workerStatus: () => [...systemKeys.all, 'worker-status'] as const,
};

/**
 * Hook to poll worker status
 * @param enabled - Whether polling is enabled (default: true)
 * @param refetchInterval - Polling interval in ms (default: 10000)
 */
export function useWorkerStatus(
  enabled = true,
  refetchInterval = 10000
): {
  status: WorkerStatusResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: systemKeys.workerStatus(),
    queryFn: () => systemApi.getWorkerStatus(),
    enabled,
    refetchInterval,
    staleTime: 5000, // Consider data stale after 5 seconds
    retry: 1, // Only retry once on failure
  });

  return {
    status: data,
    isLoading,
    isError,
    error: error as Error | null,
  };
}
