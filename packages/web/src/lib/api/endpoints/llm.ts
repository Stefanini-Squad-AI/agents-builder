import { 
  LlmRunView,
  ApiResponse 
} from '../types';
import { get, post } from '../client';

/**
 * LLM operations API endpoints
 */
export const llmApi = {
  // Get LLM runs for a project
  async getLlmRuns(projectSlug: string, params?: {
    kind?: string;
    limit?: number;
    offset?: number;
  }): Promise<{
    runs: LlmRunView[];
    total: number;
  }> {
    return get(`/api/projects/${projectSlug}/llm-runs`, params);
  },

  // Get specific LLM run
  async getLlmRun(runId: string): Promise<LlmRunView> {
    return get<LlmRunView>(`/api/llm-runs/${runId}`);
  },

  // Get LLM run details with full prompt/response
  async getLlmRunDetails(runId: string): Promise<{
    run: LlmRunView;
    prompt: {
      system: string;
      messages: Array<{
        role: string;
        content: string;
      }>;
    };
    response: {
      text?: string;
      json?: Record<string, any>;
      reasoning?: string;
    };
  }> {
    return get(`/api/llm-runs/${runId}/details`);
  },

  // Get LLM runs statistics
  async getLlmRunsStats(projectSlug: string): Promise<{
    total_runs: number;
    by_kind: Record<string, number>;
    by_status: Record<string, number>;
    by_provider: Record<string, number>;
    total_cost_usd: number;
    total_tokens_in: number;
    total_tokens_out: number;
    avg_duration_ms: number;
  }> {
    return get(`/api/projects/${projectSlug}/llm-runs/stats`);
  },

  // Cancel running LLM operation (if supported)
  async cancelLlmRun(runId: string): Promise<void> {
    return post<void>(`/api/llm-runs/${runId}/cancel`);
  },

  // Get available LLM providers and their status
  async getLlmProviders(): Promise<Array<{
    provider: string;
    name: string;
    available: boolean;
    models: Array<{
      id: string;
      name: string;
      description?: string;
      max_tokens?: number;
    }>;
    status_message?: string;
  }>> {
    return get('/api/llm/providers');
  },

  // Test LLM provider connectivity
  async testLlmProvider(provider: string, model?: string): Promise<{
    available: boolean;
    latency_ms?: number;
    error_message?: string;
  }> {
    return post('/api/llm/providers/test', { provider, model });
  },

  // Get LLM provider configuration
  async getLlmProviderConfig(provider: string): Promise<{
    provider: string;
    models: string[];
    default_model: string;
    temperature_range: [number, number];
    max_tokens: number;
    supports_reasoning: boolean;
  }> {
    return get(`/api/llm/providers/${provider}/config`);
  },

  // Estimate cost for operation
  async estimateCost(provider: string, model: string, data: {
    estimated_input_tokens: number;
    estimated_output_tokens: number;
  }): Promise<{
    estimated_cost_usd: number;
    pricing: {
      input_per_million: number;
      output_per_million: number;
    };
  }> {
    return post('/api/llm/estimate-cost', { provider, model, ...data });
  },

  // Stream LLM response (for long-running operations)
  async streamLlmOperation(endpoint: string, data: any): Promise<EventSource> {
    // This would be implemented using Server-Sent Events or WebSockets
    // For now, return a mock EventSource
    const eventSource = new EventSource(`${endpoint}?stream=true`);
    return eventSource;
  },
};

export default llmApi;