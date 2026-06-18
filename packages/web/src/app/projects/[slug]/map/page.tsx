'use client';

import { useParams, useRouter } from 'next/navigation';
import { useCallback, useMemo, useState } from 'react';
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  Node,
  Edge,
  useNodesState,
  useEdgesState,
  NodeMouseHandler,
  Panel,
} from 'reactflow';
import ELK from 'elkjs/lib/elk.bundled.js';
import 'reactflow/dist/style.css';

import { useMapVisualization, useRefreshMap, useAssignWave } from '@/lib/api/queries';
import { Button } from '@/components/ui/button';
import { 
  PackageNode, 
  ObjectNode, 
  DependencyEdge, 
  MapStatsPanel,
  PackageDrawer,
  PackageNodeData,
} from '@/components/map';
import { FlowRelationshipType, MapNode as MapNodeType } from '@/lib/api/types';
import { ArrowLeft, Loader2, RefreshCw, Map as MapIcon, Network } from 'lucide-react';

// ELK layout options for hierarchical layout
const elk = new ELK();

const elkOptions = {
  'elk.algorithm': 'layered',
  'elk.direction': 'RIGHT',
  'elk.spacing.nodeNode': '60',
  'elk.layered.spacing.nodeNodeBetweenLayers': '180',
  'elk.layered.crossingMinimization.strategy': 'LAYER_SWEEP',
  'elk.layered.nodePlacement.strategy': 'NETWORK_SIMPLEX',
};

// Custom node types
const nodeTypes = {
  package: PackageNode,
  object: ObjectNode,
};

// Custom edge types
const edgeTypes = {
  dependency: DependencyEdge,
};

// Node dimensions for layout calculation
const PACKAGE_WIDTH = 220;
const PACKAGE_HEIGHT = 100;
const OBJECT_WIDTH = 160;
const OBJECT_HEIGHT = 60;

interface LayoutedElements {
  nodes: Node[];
  edges: Edge[];
}

async function getLayoutedElements(
  mapNodes: MapNodeType[],
  mapEdges: { id: string; source: string; target: string; label?: string; animated?: boolean }[]
): Promise<LayoutedElements> {
  const graph = {
    id: 'root',
    layoutOptions: elkOptions,
    children: mapNodes.map((node) => ({
      id: node.id,
      width: node.type === 'package' ? PACKAGE_WIDTH : OBJECT_WIDTH,
      height: node.type === 'package' ? PACKAGE_HEIGHT : OBJECT_HEIGHT,
    })),
    edges: mapEdges.map((edge) => ({
      id: edge.id,
      sources: [edge.source],
      targets: [edge.target],
    })),
  };

  const layoutedGraph = await elk.layout(graph);

  const nodes: Node[] = (layoutedGraph.children || []).map((node) => {
    const mapNode = mapNodes.find((n) => n.id === node.id)!;
    return {
      id: node.id,
      type: mapNode.type,
      position: { x: node.x || 0, y: node.y || 0 },
      data: mapNode.data,
    };
  });

  const edges: Edge[] = mapEdges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: 'dependency',
    data: { 
      label: edge.label,
      relationshipType: FlowRelationshipType.DATA_FLOW,
    },
    animated: edge.animated,
  }));

  return { nodes, edges };
}

export default function MigrationMapPage() {
  const params = useParams();
  const router = useRouter();
  const projectSlug = params.slug as string;

  // Fetch map data
  const { data: mapData, isLoading, error, refetch } = useMapVisualization(projectSlug);
  
  // Mutations
  const refreshMutation = useRefreshMap(projectSlug);
  const assignWaveMutation = useAssignWave(projectSlug);

  // React Flow state
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [isLayouting, setIsLayouting] = useState(false);
  const [hasLayouted, setHasLayouted] = useState(false);

  // Drawer state
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // Get selected node data
  const selectedNode = useMemo(() => {
    if (!selectedNodeId) return null;
    const node = nodes.find((n) => n.id === selectedNodeId);
    if (!node || node.type !== 'package') return null;
    return {
      id: node.id,
      data: node.data as PackageNodeData,
    };
  }, [selectedNodeId, nodes]);

  // Layout nodes when data loads
  useMemo(() => {
    if (mapData && !hasLayouted && !isLayouting) {
      setIsLayouting(true);
      getLayoutedElements(mapData.nodes, mapData.edges)
        .then(({ nodes: layoutedNodes, edges: layoutedEdges }) => {
          setNodes(layoutedNodes);
          setEdges(layoutedEdges);
          setHasLayouted(true);
        })
        .finally(() => {
          setIsLayouting(false);
        });
    }
  }, [mapData, hasLayouted, isLayouting, setNodes, setEdges]);

  // Handle refresh
  const handleRefresh = useCallback(() => {
    refreshMutation.mutate(undefined, {
      onSuccess: () => {
        setHasLayouted(false);
        refetch();
      },
    });
  }, [refreshMutation, refetch]);

  // Handle node click
  const onNodeClick: NodeMouseHandler = useCallback((event, node) => {
    if (node.type === 'package') {
      setSelectedNodeId(node.id);
    }
  }, []);

  // Handle close drawer
  const handleCloseDrawer = useCallback(() => {
    setSelectedNodeId(null);
  }, []);

  // Handle wave change
  const handleWaveChange = useCallback((wave: number) => {
    if (!selectedNodeId) return;
    
    assignWaveMutation.mutate(
      { packageId: selectedNodeId, wave },
      {
        onSuccess: () => {
          // Update local node data
          setNodes((nds) =>
            nds.map((n) =>
              n.id === selectedNodeId
                ? { ...n, data: { ...n.data, wave } }
                : n
            )
          );
        },
      }
    );
  }, [selectedNodeId, assignWaveMutation, setNodes]);

  // Handle back navigation
  const handleBack = useCallback(() => {
    router.push(`/projects/${projectSlug}`);
  }, [router, projectSlug]);

  // Loading state
  if (isLoading || isLayouting) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-muted-foreground">
            {isLoading ? 'Loading migration map...' : 'Computing layout...'}
          </p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-4 max-w-md text-center">
          <MapIcon className="h-12 w-12 text-muted-foreground" />
          <h2 className="text-lg font-semibold">Failed to load migration map</h2>
          <p className="text-muted-foreground">
            {error instanceof Error ? error.message : 'An unexpected error occurred'}
          </p>
          <Button onClick={() => refetch()}>Retry</Button>
        </div>
      </div>
    );
  }

  // Empty state
  if (!mapData || mapData.nodes.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-4 max-w-md text-center">
          <Network className="h-12 w-12 text-muted-foreground" />
          <h2 className="text-lg font-semibold">No packages analyzed yet</h2>
          <p className="text-muted-foreground">
            Upload and analyze ETL packages to visualize the migration map.
            The map shows data flow dependencies between packages.
          </p>
          <Button onClick={handleBack}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Project
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Stats Panel */}
      <MapStatsPanel stats={mapData.stats} className="mx-4 mt-4" />

      {/* Map */}
      <div className="flex-1 mt-4">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.1}
          maxZoom={2}
        >
          <Background variant={BackgroundVariant.Dots} gap={16} />
          <Controls />
          <MiniMap 
            nodeColor={(node) => {
              if (node.type === 'package') {
                const data = node.data as PackageNodeData;
                switch (data.status) {
                  case 'analyzed': return '#22c55e';
                  case 'analyzing': return '#3b82f6';
                  case 'failed': return '#ef4444';
                  default: return '#9ca3af';
                }
              }
              return '#e5e7eb';
            }}
          />
          <Panel position="top-left">
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={handleBack}>
                <ArrowLeft className="h-4 w-4 mr-1" />
                Back
              </Button>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={handleRefresh}
                disabled={refreshMutation.isPending}
              >
                <RefreshCw className={`h-4 w-4 mr-1 ${refreshMutation.isPending ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            </div>
          </Panel>
        </ReactFlow>
      </div>

      {/* Package Drawer */}
      {selectedNode && (
        <PackageDrawer
          packageId={selectedNode.id}
          data={selectedNode.data}
          projectSlug={projectSlug}
          onClose={handleCloseDrawer}
          onWaveChange={handleWaveChange}
        />
      )}
    </div>
  );
}
