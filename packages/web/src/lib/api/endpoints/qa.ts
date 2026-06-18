import { 
  QaAnswerView,
  QaStatsView,
  QaSummaryView,
  QaReadinessView,
  QuestionMetadata,
  SetQaAnswerRequest,
} from '../types';
import { apiClient } from '../client';

/**
 * Q&A API endpoints
 */
export const qaApi = {
  // Get all Q&A answers for a project
  async getQaAnswers(projectSlug: string): Promise<QaAnswerView[]> {
    const response = await apiClient.get<QaAnswerView[]>(`/api/projects/${projectSlug}/qa`);
    return response.data;
  },

  // Get specific Q&A answer
  async getQaAnswer(projectSlug: string, questionKey: string): Promise<QaAnswerView> {
    const response = await apiClient.get<QaAnswerView>(`/api/projects/${projectSlug}/qa/${questionKey}`);
    return response.data;
  },

  // Set/update Q&A answer
  async setQaAnswer(projectSlug: string, questionKey: string, data: SetQaAnswerRequest): Promise<QaAnswerView> {
    const response = await apiClient.put<QaAnswerView>(`/api/projects/${projectSlug}/qa/${questionKey}`, data);
    return response.data;
  },

  // Get Q&A completion statistics
  async getQaStats(projectSlug: string): Promise<QaStatsView> {
    const response = await apiClient.get<QaStatsView>(`/api/projects/${projectSlug}/qa/stats`);
    return response.data;
  },

  // Get Q&A summary (rendered markdown)
  async getQaSummary(projectSlug: string): Promise<QaSummaryView> {
    const response = await apiClient.get<QaSummaryView>(`/api/projects/${projectSlug}/qa/summary`);
    return response.data;
  },

  // Get standard questions catalog
  async getStandardQuestions(): Promise<Record<string, QuestionMetadata>> {
    const response = await apiClient.get<Record<string, QuestionMetadata>>('/api/qa/standard-questions');
    return response.data;
  },

  // Check project readiness based on Q&A
  async checkProjectReadiness(projectSlug: string): Promise<QaReadinessView> {
    const response = await apiClient.get<QaReadinessView>(`/api/projects/${projectSlug}/qa/readiness`);
    return response.data;
  },
};

export default qaApi;