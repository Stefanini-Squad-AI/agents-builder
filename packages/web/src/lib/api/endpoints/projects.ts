import { 
  ProjectView, 
  CreateProjectRequest, 
  UpdateProjectRequest,
  ProjectContext,
  ValidationReport,
  ApiResponse 
} from '../types';
import { get, post, put, del } from '../client';

/**
 * Projects API endpoints
 */
export const projectsApi = {
  // List all projects
  async getProjects(): Promise<ProjectView[]> {
    return get<ProjectView[]>('/api/projects');
  },

  // Get project by slug
  async getProject(slug: string): Promise<ProjectView> {
    return get<ProjectView>(`/api/projects/${slug}`);
  },

  // Create new project
  async createProject(data: CreateProjectRequest): Promise<ProjectView> {
    return post<ProjectView, CreateProjectRequest>('/api/projects', data);
  },

  // Update existing project
  async updateProject(slug: string, data: UpdateProjectRequest): Promise<ProjectView> {
    return put<ProjectView, UpdateProjectRequest>(`/api/projects/${slug}`, data);
  },

  // Delete project
  async deleteProject(slug: string): Promise<void> {
    return del<void>(`/api/projects/${slug}`);
  },

  // Get project context for LLM operations
  async getProjectContext(slug: string): Promise<ProjectContext> {
    return get<ProjectContext>(`/api/projects/${slug}/context`);
  },

  // Validate project readiness
  async validateProject(slug: string): Promise<ValidationReport> {
    return get<ValidationReport>(`/api/projects/${slug}/validation`);
  },

  // Get project statistics/summary
  async getProjectSummary(slug: string): Promise<{
    skills_count: number;
    cards_count: number;
    phases_count: number;
    qa_completion: number;
    tech_choices_count: number;
  }> {
    return get(`/api/projects/${slug}/summary`);
  },

  // Set project as current context (for CLI integration)
  async setProjectContext(slug: string): Promise<void> {
    return post<void>(`/api/projects/${slug}/set-context`);
  },
};

export default projectsApi;