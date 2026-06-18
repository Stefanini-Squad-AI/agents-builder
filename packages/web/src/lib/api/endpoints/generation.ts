import { api } from "../client";
import type {
  GenerationOptions,
  GenerationPreview,
  GenerationResult,
  PackageDesignAnalysis,
} from "../types";

export const generationApi = {
  /**
   * Get design guidance analysis for a package
   */
  getDesignGuidance: async (
    projectRef: string,
    packageId: string
  ): Promise<PackageDesignAnalysis> => {
    const response = await api.get<PackageDesignAnalysis>(
      `/api/migrations/${projectRef}/generation/packages/${packageId}/design`
    );
    return response.data;
  },

  /**
   * Preview what would be generated (backward analysis only)
   */
  previewGeneration: async (
    projectRef: string,
    packageId: string
  ): Promise<GenerationPreview> => {
    const response = await api.get<GenerationPreview>(
      `/api/migrations/${projectRef}/generation/packages/${packageId}/preview`
    );
    return response.data;
  },

  /**
   * Generate notebook artifacts for a package
   */
  generatePackage: async (
    projectRef: string,
    packageId: string,
    options?: GenerationOptions
  ): Promise<GenerationResult> => {
    const response = await api.post<GenerationResult>(
      `/api/migrations/${projectRef}/generation/packages/${packageId}/generate`,
      options ? { options } : undefined
    );
    return response.data;
  },

  /**
   * Generate and download as ZIP bundle
   */
  downloadBundle: async (
    projectRef: string,
    packageId: string,
    options?: GenerationOptions
  ): Promise<Blob> => {
    const response = await api.post(
      `/api/migrations/${projectRef}/generation/packages/${packageId}/download`,
      options ? { options } : undefined,
      { responseType: "blob" }
    );
    return response.data;
  },
};
