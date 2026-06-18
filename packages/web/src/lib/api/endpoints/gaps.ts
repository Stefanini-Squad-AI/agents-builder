import {
  GapView,
  GapsStatsResponse,
  GapStatus,
  CreateGapRequest,
  AddressBySkillRequest,
  CoverByMcpRequest,
  OutOfScopeRequest,
} from '../types';
import { get, post, del } from '../client';

/**
 * Gaps API — project coverage gaps surfaced by ProposeSkillSet.
 *
 * A gap is a project-scoped concern flagged by the LLM (e.g. "no skill
 * covers secrets rotation"). It transitions through:
 *   open → addressed_by_skill | covered_by_mcp | out_of_scope
 */
export const gapsApi = {
  // List gaps, optionally filtered by status
  async listGaps(projectSlug: string, status?: GapStatus): Promise<GapView[]> {
    const params = status ? { status } : undefined;
    return get<GapView[]>(`/api/projects/${projectSlug}/gaps`, params);
  },

  // Stats for the gap panel header
  async getStats(projectSlug: string): Promise<GapsStatsResponse> {
    return get<GapsStatsResponse>(`/api/projects/${projectSlug}/gaps/stats`);
  },

  // Create manual gap (source=manual)
  async createGap(
    projectSlug: string,
    payload: CreateGapRequest
  ): Promise<GapView> {
    return post<GapView, CreateGapRequest>(
      `/api/projects/${projectSlug}/gaps`,
      payload
    );
  },

  // Mark gap as addressed by an existing skill in the project
  async addressBySkill(
    projectSlug: string,
    gapId: string,
    payload: AddressBySkillRequest
  ): Promise<GapView> {
    return post<GapView, AddressBySkillRequest>(
      `/api/projects/${projectSlug}/gaps/${gapId}/address-by-skill`,
      payload
    );
  },

  // Mark gap as covered by an external MCP
  async coverByMcp(
    projectSlug: string,
    gapId: string,
    payload: CoverByMcpRequest
  ): Promise<GapView> {
    return post<GapView, CoverByMcpRequest>(
      `/api/projects/${projectSlug}/gaps/${gapId}/cover-by-mcp`,
      payload
    );
  },

  // Mark gap as out of scope
  async markOutOfScope(
    projectSlug: string,
    gapId: string,
    payload: OutOfScopeRequest
  ): Promise<GapView> {
    return post<GapView, OutOfScopeRequest>(
      `/api/projects/${projectSlug}/gaps/${gapId}/out-of-scope`,
      payload
    );
  },

  // Reopen a previously resolved gap
  async reopen(projectSlug: string, gapId: string): Promise<GapView> {
    return post<GapView>(`/api/projects/${projectSlug}/gaps/${gapId}/reopen`);
  },

  // Delete a manual gap (cannot delete propose_skill_set ones)
  async deleteGap(projectSlug: string, gapId: string): Promise<void> {
    return del<void>(`/api/projects/${projectSlug}/gaps/${gapId}`);
  },
};

export default gapsApi;
