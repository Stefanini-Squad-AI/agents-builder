// System-level API endpoints (health, worker status, etc.)

import { apiClient } from '../client';
import type { WorkerStatusResponse } from '../types';

/**
 * Get the current worker infrastructure status
 */
async function getWorkerStatus(): Promise<WorkerStatusResponse> {
  const response = await apiClient.get<WorkerStatusResponse>('/api/worker-status');
  return response.data;
}

const systemApi = {
  getWorkerStatus,
};

export default systemApi;
