import {
  MCPCatalogListItem,
  MCPCatalogEntry,
  MCPConfigSummary,
  MCPConfigView,
  MCPConfigCreate,
  MCPConfigUpdate,
  MCPConfigToggle,
  MCPConfigValidation,
  MCPExportPreview,
  CursorMCPConfig,
} from '../types';
import { apiClient, get, post, patch, del } from '../client';

/**
 * MCP Catalog & Configuration API.
 *
 * Two scopes:
 *   - Catalog (global): browse all available MCP server definitions
 *   - Config (per-project): configure secrets/fields for selected MCPs,
 *     export to .cursor/mcp.json
 *
 * NOTE: Config endpoints take projectId (UUID), not slug.
 */
export const mcpApi = {
  // ===========================================================================
  // Catalog
  // ===========================================================================

  async listCatalog(category?: string): Promise<MCPCatalogListItem[]> {
    const params = category ? { category } : undefined;
    return get<MCPCatalogListItem[]>('/mcp-catalog', params);
  },

  async getCatalogEntry(key: string): Promise<MCPCatalogEntry> {
    return get<MCPCatalogEntry>(`/mcp-catalog/${key}`);
  },

  // ===========================================================================
  // Per-project configurations
  // ===========================================================================

  async listConfigs(
    projectId: string,
    enabledOnly = false
  ): Promise<MCPConfigSummary[]> {
    const params = enabledOnly ? { enabled_only: true } : undefined;
    return get<MCPConfigSummary[]>(`/projects/${projectId}/mcps`, params);
  },

  async getConfig(projectId: string, configId: string): Promise<MCPConfigView> {
    return get<MCPConfigView>(`/projects/${projectId}/mcps/${configId}`);
  },

  async createConfig(
    projectId: string,
    payload: MCPConfigCreate
  ): Promise<MCPConfigView> {
    return post<MCPConfigView, MCPConfigCreate>(
      `/projects/${projectId}/mcps`,
      payload
    );
  },

  async updateConfig(
    projectId: string,
    configId: string,
    payload: MCPConfigUpdate
  ): Promise<MCPConfigView> {
    return patch<MCPConfigView, MCPConfigUpdate>(
      `/projects/${projectId}/mcps/${configId}`,
      payload
    );
  },

  async deleteConfig(projectId: string, configId: string): Promise<void> {
    return del<void>(`/projects/${projectId}/mcps/${configId}`);
  },

  async toggleConfig(
    projectId: string,
    configId: string,
    enabled: boolean
  ): Promise<MCPConfigView> {
    return post<MCPConfigView, MCPConfigToggle>(
      `/projects/${projectId}/mcps/${configId}/toggle`,
      { enabled }
    );
  },

  async validateConfig(
    projectId: string,
    configId: string
  ): Promise<MCPConfigValidation> {
    return post<MCPConfigValidation>(
      `/projects/${projectId}/mcps/${configId}/validate`
    );
  },

  // ===========================================================================
  // Export to .cursor/mcp.json
  // ===========================================================================

  async getExportPreview(projectId: string): Promise<MCPExportPreview> {
    return get<MCPExportPreview>(
      `/projects/${projectId}/mcps/export/preview`
    );
  },

  async getExportJson(projectId: string): Promise<CursorMCPConfig> {
    return get<CursorMCPConfig>(`/projects/${projectId}/mcps/export`);
  },

  // Triggers a browser download of mcp.json
  async downloadMcpJson(projectId: string): Promise<void> {
    const response = await apiClient.get(
      `/projects/${projectId}/mcps/export/download`,
      { responseType: 'blob' }
    );
    const blob = new Blob([response.data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'mcp.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },
};

export default mcpApi;
