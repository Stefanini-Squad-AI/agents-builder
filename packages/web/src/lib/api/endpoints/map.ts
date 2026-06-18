import { 
  MapVisualization, 
  MigrationObjectView, 
  ObjectWithPackages,
  FlowDepView,
  ClusterView,
  ClusterWithMembers,
  WaveSuggestionsResult,
  MapRefreshResult,
  FlowRelationshipType,
} from '../types';
import { get, post, put, del } from '../client';

/**
 * Migration Map API endpoints
 */
export const mapApi = {
  // Get full map visualization (React Flow format)
  async getMapVisualization(projectSlug: string): Promise<MapVisualization> {
    return get<MapVisualization>(`/api/migrations/${projectSlug}/map`);
  },

  // Refresh/recompute all relationships
  async refreshMap(projectSlug: string): Promise<MapRefreshResult> {
    return post<MapRefreshResult>(`/api/migrations/${projectSlug}/map/refresh`);
  },

  // List discovered objects
  async listObjects(projectSlug: string): Promise<{ objects: MigrationObjectView[]; total: number }> {
    return get<{ objects: MigrationObjectView[]; total: number }>(`/api/migrations/${projectSlug}/map/objects`);
  },

  // Get object with packages that read/write it
  async getObject(projectSlug: string, objectId: string): Promise<ObjectWithPackages> {
    return get<ObjectWithPackages>(`/api/migrations/${projectSlug}/map/objects/${objectId}`);
  },

  // List flow dependencies
  async listDependencies(projectSlug: string): Promise<{ dependencies: FlowDepView[]; total: number }> {
    return get<{ dependencies: FlowDepView[]; total: number }>(`/api/migrations/${projectSlug}/map/deps`);
  },

  // Create manual dependency
  async createDependency(
    projectSlug: string, 
    data: {
      upstream_package_id: string;
      downstream_package_id: string;
      relationship_type?: FlowRelationshipType;
    }
  ): Promise<FlowDepView> {
    return post<FlowDepView>(`/api/migrations/${projectSlug}/map/deps`, data);
  },

  // Confirm/reject a dependency
  async confirmDependency(
    projectSlug: string, 
    depId: string, 
    data: { confirmed: boolean; rejected?: boolean }
  ): Promise<FlowDepView> {
    return put<FlowDepView>(`/api/migrations/${projectSlug}/map/deps/${depId}/confirm`, data);
  },

  // Delete a dependency
  async deleteDependency(projectSlug: string, depId: string): Promise<void> {
    return del<void>(`/api/migrations/${projectSlug}/map/deps/${depId}`);
  },

  // List clusters
  async listClusters(projectSlug: string): Promise<{ clusters: ClusterView[]; total: number }> {
    return get<{ clusters: ClusterView[]; total: number }>(`/api/migrations/${projectSlug}/map/clusters`);
  },

  // Get cluster with members
  async getCluster(projectSlug: string, clusterId: string): Promise<ClusterWithMembers> {
    return get<ClusterWithMembers>(`/api/migrations/${projectSlug}/map/clusters/${clusterId}`);
  },

  // Get wave suggestions
  async suggestWaves(projectSlug: string): Promise<WaveSuggestionsResult> {
    return post<WaveSuggestionsResult>(`/api/migrations/${projectSlug}/map/waves/suggest`);
  },

  // Assign wave to package
  async assignWave(
    projectSlug: string, 
    packageId: string, 
    wave: number
  ): Promise<{ package_id: string; wave: number }> {
    return put<{ package_id: string; wave: number }>(
      `/api/migrations/${projectSlug}/map/packages/${packageId}/wave`, 
      { wave }
    );
  },
};

export default mapApi;
