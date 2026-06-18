import { api } from "../client";
import type { SkillSummary, SkillDetail } from "../types";

/**
 * Migration Workbench pre-built skills API
 */
export const migrationSkillsApi = {
  /**
   * List all available pre-built skills
   */
  listSkills: async (): Promise<SkillSummary[]> => {
    const response = await api.get<SkillSummary[]>("/api/migrations/skills");
    return response.data;
  },

  /**
   * Get detailed information about a specific skill
   */
  getSkill: async (skillId: string): Promise<SkillDetail> => {
    const response = await api.get<SkillDetail>(
      `/api/migrations/skills/${skillId}`
    );
    return response.data;
  },
};
