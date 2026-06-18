import { ArtifactSummary, ArtifactKind } from '../types';
import { apiClient } from '../client';

// Request types
export interface UploadArtifactRequest {
  file: File;
  kind?: ArtifactKind;
  onProgress?: (progress: number) => void;
}

/**
 * Artifact API endpoints
 */
export const artifactApi = {
  // =========================================================================
  // Upload
  // =========================================================================

  /**
   * Upload a new artifact to a project
   * Returns 202 Accepted - extraction happens asynchronously
   */
  async uploadArtifact(
    projectSlug: string,
    request: UploadArtifactRequest
  ): Promise<ArtifactSummary> {
    const formData = new FormData();
    formData.append('file', request.file);
    if (request.kind) {
      formData.append('kind', request.kind);
    }

    const response = await apiClient.post<ArtifactSummary>(
      `/api/projects/${projectSlug}/artifacts`,
      formData,
      {
        // Don't set Content-Type - axios will set it automatically with boundary for FormData
        headers: {
          'Content-Type': undefined,
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total && request.onProgress) {
            const progress = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total
            );
            request.onProgress(progress);
          }
        },
      }
    );
    return response.data;
  },

  // =========================================================================
  // List & Get
  // =========================================================================

  /**
   * List all artifacts for a project
   */
  async listProjectArtifacts(projectSlug: string): Promise<ArtifactSummary[]> {
    const response = await apiClient.get<ArtifactSummary[]>(
      `/api/projects/${projectSlug}/artifacts`
    );
    return response.data;
  },

  /**
   * Get a single artifact by ID (for polling status)
   */
  async getArtifact(artifactId: string): Promise<ArtifactSummary> {
    const response = await apiClient.get<ArtifactSummary>(
      `/api/artifacts/${artifactId}`
    );
    return response.data;
  },

  // =========================================================================
  // Actions
  // =========================================================================

  /**
   * Retry extraction for a failed artifact
   */
  async retryArtifact(artifactId: string): Promise<ArtifactSummary> {
    const response = await apiClient.post<ArtifactSummary>(
      `/api/artifacts/${artifactId}/retry`
    );
    return response.data;
  },

  /**
   * Delete an artifact
   */
  async deleteArtifact(artifactId: string): Promise<void> {
    await apiClient.delete(`/api/artifacts/${artifactId}`);
  },
};

export default artifactApi;
