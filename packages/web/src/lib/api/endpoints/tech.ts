import { 
  TechDimensionView,
  TechItemView, 
  TechChoiceView,
  TechChoiceRole,
} from '../types';
import { apiClient } from '../client';

// Request types
export interface SetTechChoiceRequest {
  role: TechChoiceRole;
  notes?: string;
}

export interface AddCustomItemRequest {
  name: string;
  role: TechChoiceRole;
  description?: string;
  tags?: string[];
  notes?: string;
}

export interface MarkTbdRequest {
  notes?: string;
}

// Response types
export interface TechStatsResponse {
  total_choices: number;
  by_role: Record<string, number>;
  by_source: Record<string, number>;
  by_dimension: Record<string, number>;
  coverage_percentage: number;
  covered_dimensions: number;
  total_dimensions: number;
  tbd_dimensions: number;
  pending_suggestions: number;
}

export interface TechSummaryResponse {
  summary_md: string;
}

export interface DimensionWithChoices {
  id: string;
  slug: string;
  name: string;
  description?: string;
  order_no: number;
  items: TechItemView[];
  choices: TechChoiceView[];
}

/**
 * Tech panorama API endpoints
 */
export const techApi = {
  // =========================================================================
  // Catalog endpoints (read-only)
  // =========================================================================
  
  // Get all tech dimensions with items
  async getTechDimensions(): Promise<TechDimensionView[]> {
    const response = await apiClient.get<TechDimensionView[]>('/api/tech/dimensions');
    return response.data;
  },

  // Get specific tech dimension
  async getTechDimension(dimensionSlug: string): Promise<TechDimensionView> {
    const response = await apiClient.get<TechDimensionView>(`/api/tech/dimensions/${dimensionSlug}`);
    return response.data;
  },

  // =========================================================================
  // Project tech choice endpoints
  // =========================================================================
  
  // Get project tech choices
  async getProjectTechChoices(projectSlug: string): Promise<TechChoiceView[]> {
    const response = await apiClient.get<TechChoiceView[]>(`/api/projects/${projectSlug}/tech`);
    return response.data;
  },

  // Get all dimensions with project choices
  async getDimensionsWithChoices(projectSlug: string): Promise<DimensionWithChoices[]> {
    const response = await apiClient.get<DimensionWithChoices[]>(`/api/projects/${projectSlug}/tech/dimensions`);
    return response.data;
  },

  // Get tech choices for specific dimension
  async getDimensionChoices(projectSlug: string, dimensionSlug: string): Promise<TechChoiceView[]> {
    const response = await apiClient.get<TechChoiceView[]>(`/api/projects/${projectSlug}/tech/${dimensionSlug}`);
    return response.data;
  },

  // Get tech statistics
  async getTechStats(projectSlug: string): Promise<TechStatsResponse> {
    const response = await apiClient.get<TechStatsResponse>(`/api/projects/${projectSlug}/tech/stats`);
    return response.data;
  },

  // Get tech summary (rendered markdown)
  async getTechSummary(projectSlug: string): Promise<TechSummaryResponse> {
    const response = await apiClient.get<TechSummaryResponse>(`/api/projects/${projectSlug}/tech/summary`);
    return response.data;
  },

  // Set tech choice for dimension/item
  async setTechChoice(
    projectSlug: string, 
    dimensionSlug: string, 
    itemSlug: string, 
    data: SetTechChoiceRequest
  ): Promise<TechChoiceView> {
    const response = await apiClient.put<TechChoiceView>(
      `/api/projects/${projectSlug}/tech/${dimensionSlug}/${itemSlug}`, 
      data
    );
    return response.data;
  },

  // Remove tech choice
  async removeTechChoice(projectSlug: string, dimensionSlug: string, itemSlug: string): Promise<void> {
    await apiClient.delete(`/api/projects/${projectSlug}/tech/${dimensionSlug}/${itemSlug}`);
  },

  // Mark dimension as TBD (to be determined)
  async markTbd(projectSlug: string, dimensionSlug: string, data?: MarkTbdRequest): Promise<TechChoiceView> {
    const response = await apiClient.put<TechChoiceView>(
      `/api/projects/${projectSlug}/tech/${dimensionSlug}/tbd`, 
      data || {}
    );
    return response.data;
  },

  // Clear TBD marking
  async clearTbd(projectSlug: string, dimensionSlug: string): Promise<void> {
    await apiClient.delete(`/api/projects/${projectSlug}/tech/${dimensionSlug}/tbd`);
  },

  // Add custom tech item
  async addCustomItem(
    projectSlug: string, 
    dimensionSlug: string, 
    data: AddCustomItemRequest
  ): Promise<TechChoiceView> {
    const response = await apiClient.post<TechChoiceView>(
      `/api/projects/${projectSlug}/tech/${dimensionSlug}/custom`, 
      data
    );
    return response.data;
  },

  // Accept LLM suggestion
  async acceptSuggestion(
    projectSlug: string, 
    dimensionSlug: string, 
    itemSlug: string
  ): Promise<TechChoiceView> {
    const response = await apiClient.post<TechChoiceView>(
      `/api/projects/${projectSlug}/tech/${dimensionSlug}/accept`,
      { item_slug: itemSlug }
    );
    return response.data;
  },

  // Dismiss LLM suggestion
  async dismissSuggestion(
    projectSlug: string, 
    dimensionSlug: string, 
    itemSlug: string
  ): Promise<void> {
    await apiClient.post(
      `/api/projects/${projectSlug}/tech/${dimensionSlug}/dismiss`,
      { item_slug: itemSlug }
    );
  },
};

export default techApi;