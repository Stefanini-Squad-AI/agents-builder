import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { mcpApi } from '../endpoints';
import { queryKeys } from '../../query-client';
import {
  MCPConfigCreate,
  MCPConfigUpdate,
} from '../types';

function invalidateProjectMcpCaches(
  queryClient: ReturnType<typeof useQueryClient>,
  projectId: string
) {
  queryClient.invalidateQueries({
    queryKey: ['projects', projectId, 'mcps'],
  });
}

// =============================================================================
// Catalog (global)
// =============================================================================

export function useMcpCatalog(category?: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.mcpCatalog(category),
    queryFn: () => mcpApi.listCatalog(category),
    enabled,
    // Catalog is static — we can hold longer.
    staleTime: 30 * 60 * 1000,
  });
}

export function useMcpCatalogEntry(key: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.mcpCatalogEntry(key),
    queryFn: () => mcpApi.getCatalogEntry(key),
    enabled: enabled && !!key,
    staleTime: 30 * 60 * 1000,
  });
}

// =============================================================================
// Configurations (per project, projectId is UUID)
// =============================================================================

export function useMcpConfigs(
  projectId: string,
  enabledOnly = false,
  enabled = true
) {
  return useQuery({
    queryKey: queryKeys.mcpConfigs(projectId, enabledOnly),
    queryFn: () => mcpApi.listConfigs(projectId, enabledOnly),
    enabled: enabled && !!projectId,
    staleTime: 60 * 1000,
  });
}

export function useMcpConfig(
  projectId: string,
  configId: string,
  enabled = true
) {
  return useQuery({
    queryKey: queryKeys.mcpConfig(projectId, configId),
    queryFn: () => mcpApi.getConfig(projectId, configId),
    enabled: enabled && !!projectId && !!configId,
    staleTime: 60 * 1000,
  });
}

export function useCreateMcpConfig(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: MCPConfigCreate) =>
      mcpApi.createConfig(projectId, payload),
    onSuccess: (config) => {
      invalidateProjectMcpCaches(queryClient, projectId);
      toast.success(`${config.mcp_name} configured`);
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to configure MCP');
    },
  });
}

export function useUpdateMcpConfig(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      configId,
      payload,
    }: {
      configId: string;
      payload: MCPConfigUpdate;
    }) => mcpApi.updateConfig(projectId, configId, payload),
    onSuccess: () => {
      invalidateProjectMcpCaches(queryClient, projectId);
      toast.success('MCP configuration updated');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to update MCP');
    },
  });
}

export function useDeleteMcpConfig(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (configId: string) =>
      mcpApi.deleteConfig(projectId, configId),
    onSuccess: () => {
      invalidateProjectMcpCaches(queryClient, projectId);
      toast.success('MCP configuration removed');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to remove MCP');
    },
  });
}

export function useToggleMcpConfig(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      configId,
      enabled,
    }: {
      configId: string;
      enabled: boolean;
    }) => mcpApi.toggleConfig(projectId, configId, enabled),
    onSuccess: (config) => {
      invalidateProjectMcpCaches(queryClient, projectId);
      toast.success(`${config.mcp_name} ${config.enabled ? 'enabled' : 'disabled'}`);
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to toggle MCP');
    },
  });
}

export function useValidateMcpConfig(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (configId: string) =>
      mcpApi.validateConfig(projectId, configId),
    onSuccess: (result) => {
      invalidateProjectMcpCaches(queryClient, projectId);
      if (result.valid) {
        toast.success('MCP configuration is valid');
      } else {
        toast.error(
          result.errors.length
            ? `Validation failed: ${result.errors.join(', ')}`
            : 'Validation failed'
        );
      }
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to validate MCP');
    },
  });
}

// =============================================================================
// Export
// =============================================================================

export function useMcpExportPreview(projectId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.mcpExportPreview(projectId),
    queryFn: () => mcpApi.getExportPreview(projectId),
    enabled: enabled && !!projectId,
    staleTime: 30 * 1000,
  });
}

/**
 * Trigger a browser download of mcp.json. Not a hook — call directly.
 */
export async function downloadMcpJson(projectId: string): Promise<void> {
  try {
    await mcpApi.downloadMcpJson(projectId);
    toast.success('mcp.json downloaded');
  } catch (error) {
    const message =
      error instanceof Error ? error.message : 'Failed to download mcp.json';
    toast.error(message);
    throw error;
  }
}
