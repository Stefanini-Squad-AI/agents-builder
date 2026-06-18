import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { projectsApi } from '../endpoints';
import { queryKeys, invalidateProjects, invalidateProject, removeProject } from '../../query-client';
import { ProjectView, CreateProjectRequest, UpdateProjectRequest, ProjectContext, ValidationReport } from '../types';

/**
 * Hook to fetch all projects
 */
export function useProjects() {
  return useQuery({
    queryKey: queryKeys.projects,
    queryFn: () => projectsApi.getProjects(),
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}

/**
 * Hook to fetch a specific project
 */
export function useProject(slug: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.project(slug),
    queryFn: () => projectsApi.getProject(slug),
    enabled: enabled && !!slug,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to fetch project context
 */
export function useProjectContext(slug: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.projectContext(slug),
    queryFn: () => projectsApi.getProjectContext(slug),
    enabled: enabled && !!slug,
    staleTime: 1 * 60 * 1000, // 1 minute (context changes frequently)
  });
}

/**
 * Hook to validate project
 */
export function useProjectValidation(slug: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.projectValidation(slug),
    queryFn: () => projectsApi.validateProject(slug),
    enabled: enabled && !!slug,
    staleTime: 30 * 1000, // 30 seconds (validation should be fresh)
  });
}

/**
 * Hook to create a new project
 */
export function useCreateProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateProjectRequest) => projectsApi.createProject(data),
    onSuccess: (newProject) => {
      // Invalidate projects list
      invalidateProjects();
      
      // Add the new project to the cache
      queryClient.setQueryData(queryKeys.project(newProject.slug), newProject);
    },
    onError: (error) => {
      console.error('Failed to create project:', error);
    },
  });
}

/**
 * Hook to update a project
 */
export function useUpdateProject(slug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateProjectRequest) => projectsApi.updateProject(slug, data),
    onMutate: async (newData) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: queryKeys.project(slug) });

      // Snapshot previous value
      const previousProject = queryClient.getQueryData<ProjectView>(queryKeys.project(slug));

      // Optimistically update
      if (previousProject) {
        queryClient.setQueryData<ProjectView>(queryKeys.project(slug), {
          ...previousProject,
          ...newData,
          updated_at: new Date().toISOString(),
        });
      }

      return { previousProject };
    },
    onError: (error, newData, context) => {
      // Rollback on error
      if (context?.previousProject) {
        queryClient.setQueryData(queryKeys.project(slug), context.previousProject);
      }
      console.error('Failed to update project:', error);
    },
    onSettled: () => {
      // Always refetch after error or success
      invalidateProject(slug);
      invalidateProjects();
    },
  });
}

/**
 * Hook to delete a project
 */
export function useDeleteProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (slug: string) => projectsApi.deleteProject(slug),
    onSuccess: (_, deletedSlug) => {
      // Remove from cache
      removeProject(deletedSlug);
      
      // Invalidate projects list
      invalidateProjects();
    },
    onError: (error) => {
      console.error('Failed to delete project:', error);
    },
  });
}

/**
 * Hook to get project summary/stats
 */
export function useProjectSummary(slug: string, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.project(slug), 'summary'],
    queryFn: () => projectsApi.getProjectSummary(slug),
    enabled: enabled && !!slug,
    staleTime: 1 * 60 * 1000, // 1 minute
  });
}

/**
 * Hook to set project as current context
 */
export function useSetProjectContext() {
  return useMutation({
    mutationFn: (slug: string) => projectsApi.setProjectContext(slug),
    onError: (error) => {
      console.error('Failed to set project context:', error);
    },
  });
}