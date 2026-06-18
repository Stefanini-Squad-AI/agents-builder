import { QueryClient } from '@tanstack/react-query';

// Global query client configuration
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Stale time: Data is considered fresh for 5 minutes
      staleTime: 5 * 60 * 1000,
      
      // Cache time: Data stays in cache for 10 minutes after becoming unused
      gcTime: 10 * 60 * 1000,
      
      // Retry failed requests 3 times with exponential backoff
      retry: (failureCount, error) => {
        // Don't retry on 4xx errors (client errors)
        if (error instanceof Error && error.message.includes('4')) {
          return false;
        }
        return failureCount < 3;
      },
      
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      
      // Refetch on window focus for important data
      refetchOnWindowFocus: true,
      
      // Don't refetch on reconnect by default (can be overridden per query)
      refetchOnReconnect: true,
      
      // Don't refetch on mount if data is still fresh
      refetchOnMount: true,
    },
    mutations: {
      // Retry mutations once on failure
      retry: 1,
      
      retryDelay: 1000,
    },
  },
});

// Query keys factory for consistent key management
export const queryKeys = {
  // Projects
  projects: ['projects'] as const,
  project: (slug: string) => ['projects', slug] as const,
  projectContext: (slug: string) => ['projects', slug, 'context'] as const,
  projectValidation: (slug: string) => ['projects', slug, 'validation'] as const,
  
  // Skills
  skills: (projectSlug: string) => ['projects', projectSlug, 'skills'] as const,
  skill: (projectSlug: string, skillId: string) => ['projects', projectSlug, 'skills', skillId] as const,
  
  // Cards
  cards: (projectSlug: string) => ['projects', projectSlug, 'cards'] as const,
  card: (projectSlug: string, cardId: string) => ['projects', projectSlug, 'cards', cardId] as const,
  
  // Phases
  phases: (projectSlug: string) => ['projects', projectSlug, 'phases'] as const,
  phase: (projectSlug: string, phaseId: string) => ['projects', projectSlug, 'phases', phaseId] as const,
  
  // Q&A
  qa: (projectSlug: string) => ['projects', projectSlug, 'qa'] as const,
  
  // Tech panorama
  techDimensions: ['tech-dimensions'] as const,
  techChoices: (projectSlug: string) => ['projects', projectSlug, 'tech-choices'] as const,
  
  // Artifacts
  artifacts: (projectSlug: string) => ['projects', projectSlug, 'artifacts'] as const,
  artifact: (artifactId: string) => ['artifacts', artifactId] as const,
  
  // LLM runs
  llmRuns: (projectSlug: string) => ['projects', projectSlug, 'llm-runs'] as const,
  llmRun: (runId: string) => ['llm-runs', runId] as const,
  
  // Exports
  exports: (projectSlug: string) => ['projects', projectSlug, 'exports'] as const,
  
  // Migration Map
  mapVisualization: (projectSlug: string) => ['projects', projectSlug, 'map'] as const,
  mapObjects: (projectSlug: string) => ['projects', projectSlug, 'map', 'objects'] as const,
  mapObject: (projectSlug: string, objectId: string) => ['projects', projectSlug, 'map', 'objects', objectId] as const,
  mapDependencies: (projectSlug: string) => ['projects', projectSlug, 'map', 'deps'] as const,
  mapClusters: (projectSlug: string) => ['projects', projectSlug, 'map', 'clusters'] as const,
  mapCluster: (projectSlug: string, clusterId: string) => ['projects', projectSlug, 'map', 'clusters', clusterId] as const,

  // Gaps (per project)
  gaps: (projectSlug: string, status?: string) =>
    status
      ? (['projects', projectSlug, 'gaps', { status }] as const)
      : (['projects', projectSlug, 'gaps'] as const),
  gapsStats: (projectSlug: string) => ['projects', projectSlug, 'gaps', 'stats'] as const,

  // MCP catalog (global)
  mcpCatalog: (category?: string) =>
    category ? (['mcp-catalog', { category }] as const) : (['mcp-catalog'] as const),
  mcpCatalogEntry: (key: string) => ['mcp-catalog', key] as const,

  // MCP configurations (per project, by projectId UUID)
  mcpConfigs: (projectId: string, enabledOnly = false) =>
    enabledOnly
      ? (['projects', projectId, 'mcps', { enabledOnly: true }] as const)
      : (['projects', projectId, 'mcps'] as const),
  mcpConfig: (projectId: string, configId: string) =>
    ['projects', projectId, 'mcps', configId] as const,
  mcpExportPreview: (projectId: string) =>
    ['projects', projectId, 'mcps', 'export', 'preview'] as const,
} as const;

// Utility functions for cache management

/**
 * Invalidate all project-related queries
 */
export function invalidateProject(projectSlug: string) {
  queryClient.invalidateQueries({ queryKey: ['projects', projectSlug] });
}

/**
 * Invalidate all projects list
 */
export function invalidateProjects() {
  queryClient.invalidateQueries({ queryKey: ['projects'] });
}

/**
 * Remove project from cache (useful after deletion)
 */
export function removeProject(projectSlug: string) {
  queryClient.removeQueries({ queryKey: ['projects', projectSlug] });
}

/**
 * Prefetch project data
 */
export function prefetchProject(projectSlug: string) {
  // This would be implemented with actual API calls
  // queryClient.prefetchQuery({
  //   queryKey: queryKeys.project(projectSlug),
  //   queryFn: () => projectsApi.getProject(projectSlug),
  // });
}

/**
 * Optimistically update project in cache
 */
export function updateProjectCache(projectSlug: string, updater: (old: any) => any) {
  queryClient.setQueryData(queryKeys.project(projectSlug), updater);
}

/**
 * Clear all cached data (useful for logout)
 */
export function clearAllCache() {
  queryClient.clear();
}

// Error boundary integration
export function handleQueryError(error: Error) {
  console.error('Query error:', error);
  
  // You could add global error handling here
  // For example: toast notifications, error tracking, etc.
}

export default queryClient;