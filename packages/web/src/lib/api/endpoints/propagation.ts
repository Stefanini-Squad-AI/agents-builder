import { 
  PropagationPreview,
  PropagationResult,
  PropagationScope,
  BatchWaveAssignment,
  BatchWaveResult,
} from '../types';
import { get, post } from '../client';

/**
 * Propagation API endpoints
 */
export const propagationApi = {
  // Preview what would be affected by propagating a decision
  async previewPropagation(
    projectSlug: string, 
    decisionId: string,
    scope: PropagationScope = PropagationScope.PROJECT,
    clusterId?: string,
    domain?: string,
  ): Promise<PropagationPreview> {
    const params = new URLSearchParams({ scope });
    if (clusterId) params.append('cluster_id', clusterId);
    if (domain) params.append('domain', domain);
    
    return get<PropagationPreview>(
      `/api/migrations/${projectSlug}/propagation/decisions/${decisionId}/preview?${params}`
    );
  },

  // Propagate a decision to matching packages
  async propagateDecision(
    projectSlug: string,
    decisionId: string,
    scope: PropagationScope = PropagationScope.PROJECT,
    clusterId?: string,
    domain?: string,
  ): Promise<PropagationResult> {
    return post<PropagationResult>(
      `/api/migrations/${projectSlug}/propagation/decisions/${decisionId}/propagate`,
      { scope, cluster_id: clusterId, domain }
    );
  },

  // Batch assign waves to multiple packages
  async batchAssignWaves(
    projectSlug: string,
    assignments: Array<{ package_id: string; wave: number }>,
  ): Promise<BatchWaveResult> {
    return post<BatchWaveResult>(
      `/api/migrations/${projectSlug}/propagation/waves/batch`,
      { assignments } as BatchWaveAssignment
    );
  },
};

export default propagationApi;
