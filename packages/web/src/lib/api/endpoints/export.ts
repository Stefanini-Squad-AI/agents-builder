import { 
  ExportView,
  ExportKind,
  ApiResponse,
  ValidationResponse,
  ExportPreviewResponse,
} from '../types';
import { get, post, del } from '../client';
import { downloadFile } from '../client';

/**
 * Export API endpoints
 */
export const exportApi = {
  // Validate project before export
  async validateProject(projectSlug: string): Promise<ValidationResponse> {
    return post<ValidationResponse>(`/api/projects/${projectSlug}/validate`);
  },

  // Get export tree preview
  async getExportPreview(projectSlug: string): Promise<ExportPreviewResponse> {
    return get<ExportPreviewResponse>(`/api/projects/${projectSlug}/export/preview`);
  },

  // Export project as ZIP file (downloads to browser)
  async exportToZip(projectSlug: string): Promise<void> {
    const filename = `${projectSlug}.agents.zip`;
    return downloadFile(`/api/projects/${projectSlug}/export/zip`, filename);
  },

  // Get project exports history
  async getExports(projectSlug: string): Promise<ExportView[]> {
    return get<ExportView[]>(`/api/projects/${projectSlug}/exports`);
  },

  // Get specific export
  async getExport(projectSlug: string, exportId: string): Promise<ExportView> {
    return get<ExportView>(`/api/projects/${projectSlug}/exports/${exportId}`);
  },

  // Export project to filesystem (creates files in backend)
  async exportToFilesystem(projectSlug: string, targetPath?: string): Promise<{
    export: ExportView;
    files_created: string[];
    summary: {
      skills_count: number;
      cards_count: number;
      phases_count: number;
      total_files: number;
    };
  }> {
    return post(`/api/projects/${projectSlug}/export/filesystem`, { 
      target_path: targetPath 
    });
  },

  // Export project as Jira CSV
  async exportToJiraCsv(projectSlug: string): Promise<void> {
    const filename = `${projectSlug}-jira-import.csv`;
    return downloadFile(`/api/projects/${projectSlug}/export/jira-csv`, filename);
  },

  // Download existing export file
  async downloadExport(projectSlug: string, exportId: string): Promise<void> {
    const exportData = await this.getExport(projectSlug, exportId);
    let filename = `${projectSlug}-export`;
    
    switch (exportData.kind) {
      case ExportKind.ZIP:
        filename += '.zip';
        break;
      case ExportKind.JIRA_CSV:
        filename += '.csv';
        break;
      default:
        filename += '.tar.gz';
    }

    return downloadFile(`/api/projects/${projectSlug}/exports/${exportId}/download`, filename);
  },

  // Delete export
  async deleteExport(projectSlug: string, exportId: string): Promise<void> {
    return del(`/api/projects/${projectSlug}/exports/${exportId}`);
  },

  // Get export statistics
  async getExportStats(projectSlug: string): Promise<{
    total_exports: number;
    by_kind: Record<string, number>;
    last_export_date?: string;
    total_size_bytes: number;
  }> {
    return get(`/api/projects/${projectSlug}/exports/stats`);
  },

  // Validate project for export
  async validateForExport(projectSlug: string, kind: ExportKind): Promise<{
    valid: boolean;
    issues: Array<{
      severity: 'error' | 'warning' | 'info';
      message: string;
      component?: string;
    }>;
    requirements: {
      min_skills?: number;
      min_cards?: number;
      required_sections?: string[];
    };
  }> {
    return get(`/api/projects/${projectSlug}/export/${kind}/validate`);
  },

  // Get available export formats
  async getExportFormats(): Promise<Array<{
    kind: ExportKind;
    name: string;
    description: string;
    file_extension: string;
    supports_streaming: boolean;
  }>> {
    return get('/api/export/formats');
  },
};

export default exportApi;