import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { generationApi } from "../endpoints/generation";
import type { GenerationOptions } from "../types";

/**
 * Query key factory for generation
 */
export const generationKeys = {
  all: ["generation"] as const,
  design: (projectRef: string, packageId: string) =>
    [...generationKeys.all, "design", projectRef, packageId] as const,
  preview: (projectRef: string, packageId: string) =>
    [...generationKeys.all, "preview", projectRef, packageId] as const,
};

/**
 * Hook to get design guidance (pattern classification and recommendations)
 */
export function useDesignGuidance(projectRef: string, packageId: string) {
  return useQuery({
    queryKey: generationKeys.design(projectRef, packageId),
    queryFn: () => generationApi.getDesignGuidance(projectRef, packageId),
    enabled: !!projectRef && !!packageId,
  });
}

/**
 * Hook to preview generation (backward analysis only)
 */
export function useGenerationPreview(projectRef: string, packageId: string) {
  return useQuery({
    queryKey: generationKeys.preview(projectRef, packageId),
    queryFn: () => generationApi.previewGeneration(projectRef, packageId),
    enabled: !!projectRef && !!packageId,
  });
}

/**
 * Hook to generate notebook artifacts
 */
export function useGeneratePackage(projectRef: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      packageId,
      options,
    }: {
      packageId: string;
      options?: GenerationOptions;
    }) => generationApi.generatePackage(projectRef, packageId, options),
    onSuccess: (_, variables) => {
      // Invalidate package queries to reflect new status
      queryClient.invalidateQueries({ queryKey: ["map", projectRef] });
      queryClient.invalidateQueries({
        queryKey: generationKeys.preview(projectRef, variables.packageId),
      });
    },
  });
}

/**
 * Hook to download generated bundle as ZIP
 */
export function useDownloadBundle(projectRef: string) {
  return useMutation({
    mutationFn: ({
      packageId,
      options,
    }: {
      packageId: string;
      options?: GenerationOptions;
    }) => generationApi.downloadBundle(projectRef, packageId, options),
    onSuccess: (blob, variables) => {
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${variables.packageId}_bundle.zip`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    },
  });
}
