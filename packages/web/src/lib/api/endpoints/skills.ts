import {
  SkillView,
  SkillResourceView,
  SkillKind,
  CreateSkillRequest,
  UpdateSkillRequest,
  BulkCreateSkillsRequest,
  BulkCreateSkillsResponse,
  ProposeSkillsResponse,
  SkillStatsResponse,
  DraftSkillBodyRequest,
  DraftSkillBodyResponse,
  DraftAllSkillsRequest,
  DraftAllSkillsResponse,
  CreateResourceRequest,
  UpdateResourceRequest,
} from '../types';
import { apiClient } from '../client';

/**
 * Skills API endpoints
 */
export const skillsApi = {
  // =========================================================================
  // List & Get
  // =========================================================================

  /**
   * List all skills for a project
   */
  async listProjectSkills(projectSlug: string): Promise<SkillView[]> {
    const response = await apiClient.get<SkillView[]>(
      `/api/projects/${projectSlug}/skills`
    );
    return response.data;
  },

  /**
   * Get skill statistics for a project
   */
  async getSkillStats(projectSlug: string): Promise<SkillStatsResponse> {
    const response = await apiClient.get<SkillStatsResponse>(
      `/api/projects/${projectSlug}/skills/stats`
    );
    return response.data;
  },

  /**
   * Get a single skill with its resources
   */
  async getSkill(projectSlug: string, skillSlug: string): Promise<SkillView> {
    const response = await apiClient.get<SkillView>(
      `/api/projects/${projectSlug}/skills/${skillSlug}`
    );
    return response.data;
  },

  // =========================================================================
  // Create & Update
  // =========================================================================

  /**
   * Create a new skill
   */
  async createSkill(
    projectSlug: string,
    request: CreateSkillRequest
  ): Promise<SkillView> {
    const response = await apiClient.post<SkillView>(
      `/api/projects/${projectSlug}/skills`,
      request
    );
    return response.data;
  },

  /**
   * Update an existing skill
   */
  async updateSkill(
    projectSlug: string,
    skillSlug: string,
    request: UpdateSkillRequest
  ): Promise<SkillView> {
    const response = await apiClient.patch<SkillView>(
      `/api/projects/${projectSlug}/skills/${skillSlug}`,
      request
    );
    return response.data;
  },

  /**
   * Delete a skill
   */
  async deleteSkill(projectSlug: string, skillSlug: string): Promise<void> {
    await apiClient.delete(`/api/projects/${projectSlug}/skills/${skillSlug}`);
  },

  // =========================================================================
  // LLM Proposal
  // =========================================================================

  /**
   * Propose a skill set using LLM
   * This gathers project context and generates 5-10 skill suggestions
   */
  async proposeSkills(projectSlug: string): Promise<ProposeSkillsResponse> {
    const response = await apiClient.post<ProposeSkillsResponse>(
      `/api/projects/${projectSlug}/skills/propose`
    );
    return response.data;
  },

  /**
   * Bulk create skills (typically from proposals)
   */
  async bulkCreateSkills(
    projectSlug: string,
    request: BulkCreateSkillsRequest
  ): Promise<BulkCreateSkillsResponse> {
    const response = await apiClient.post<BulkCreateSkillsResponse>(
      `/api/projects/${projectSlug}/skills/bulk`,
      request
    );
    return response.data;
  },

  // =========================================================================
  // Draft Skill Body (LLM)
  // =========================================================================

  /**
   * Draft/regenerate skill body using LLM
   */
  async draftSkillBody(
    projectSlug: string,
    skillSlug: string,
    request: DraftSkillBodyRequest = {}
  ): Promise<DraftSkillBodyResponse> {
    const response = await apiClient.post<DraftSkillBodyResponse>(
      `/api/projects/${projectSlug}/skills/${skillSlug}/draft`,
      request
    );
    return response.data;
  },

  /**
   * Draft all skills that need drafting (empty body_md)
   * Queues background jobs for each skill
   */
  async draftAllSkills(
    projectSlug: string,
    request: DraftAllSkillsRequest = {}
  ): Promise<DraftAllSkillsResponse> {
    const response = await apiClient.post<DraftAllSkillsResponse>(
      `/api/projects/${projectSlug}/skills/draft-all`,
      request
    );
    return response.data;
  },

  // =========================================================================
  // Skill Resources CRUD
  // =========================================================================

  /**
   * List all resources for a skill
   */
  async listSkillResources(
    projectSlug: string,
    skillSlug: string
  ): Promise<SkillResourceView[]> {
    const response = await apiClient.get<SkillResourceView[]>(
      `/api/projects/${projectSlug}/skills/${skillSlug}/resources`
    );
    return response.data;
  },

  /**
   * Create a new skill resource
   */
  async createSkillResource(
    projectSlug: string,
    skillSlug: string,
    request: CreateResourceRequest
  ): Promise<SkillResourceView> {
    const response = await apiClient.post<SkillResourceView>(
      `/api/projects/${projectSlug}/skills/${skillSlug}/resources`,
      request
    );
    return response.data;
  },

  /**
   * Update a skill resource
   */
  async updateSkillResource(
    projectSlug: string,
    skillSlug: string,
    resourceId: string,
    request: UpdateResourceRequest
  ): Promise<SkillResourceView> {
    const response = await apiClient.patch<SkillResourceView>(
      `/api/projects/${projectSlug}/skills/${skillSlug}/resources/${resourceId}`,
      request
    );
    return response.data;
  },

  /**
   * Delete a skill resource
   */
  async deleteSkillResource(
    projectSlug: string,
    skillSlug: string,
    resourceId: string
  ): Promise<void> {
    await apiClient.delete(
      `/api/projects/${projectSlug}/skills/${skillSlug}/resources/${resourceId}`
    );
  },

  // =========================================================================
  // Legacy aliases for backward compatibility
  // =========================================================================

  /** @deprecated Use listProjectSkills */
  async getSkills(projectSlug: string): Promise<SkillView[]> {
    return this.listProjectSkills(projectSlug);
  },

  /** @deprecated Use getSkillStats */
  async getSkillsStats(projectSlug: string): Promise<SkillStatsResponse> {
    return this.getSkillStats(projectSlug);
  },
};

export default skillsApi;