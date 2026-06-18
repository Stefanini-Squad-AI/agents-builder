import { useQuery } from "@tanstack/react-query";
import { migrationSkillsApi } from "../endpoints/migration-skills";

/**
 * Query key factory for migration workbench skills
 */
export const migrationSkillKeys = {
  all: ["migration-skills"] as const,
  list: () => [...migrationSkillKeys.all, "list"] as const,
  detail: (skillId: string) =>
    [...migrationSkillKeys.all, "detail", skillId] as const,
};

/**
 * Hook to list all available pre-built skills
 */
export function useMigrationSkills() {
  return useQuery({
    queryKey: migrationSkillKeys.list(),
    queryFn: () => migrationSkillsApi.listSkills(),
  });
}

/**
 * Hook to get a specific skill's details
 */
export function useMigrationSkill(skillId: string) {
  return useQuery({
    queryKey: migrationSkillKeys.detail(skillId),
    queryFn: () => migrationSkillsApi.getSkill(skillId),
    enabled: !!skillId,
  });
}
