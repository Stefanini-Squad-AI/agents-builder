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

import { useProjectDag } from '@/lib/api/queries';
import { Button } from '@/components/ui/button';
import { CardDrawer } from '@/components/dag/card-drawer';
import { CardNode } from '@/components/dag/card-node';
import { DependencyEdge } from '@/components/dag/dependency-edge';
import { DagNodeView, CardDepRelation } from '@/lib/api/types';
import { ArrowLeft, Loader2, Network } from 'lucide-react';

// ELK layout options for top-down hierarchical layout
const elk = new ELK();

const elkOptions = {
  'elk.algorithm': 'layered',
  'elk.direction': 'RIGHT',
  'elk.spacing.nodeNode': '50',
  'elk.layered.spacing.nodeNodeBetweenLayers': '150',
  'elk.layered.crossingMinimization.strategy': 'LAYER_SWEEP',
};

// Custom node types
const nodeTypes = {
  card: CardNode,
};

// Custom edge types
const edgeTypes = {
  dependency: DependencyEdge,
};

// Node dimensions for layout calculation
const NODE_WIDTH = 220;
const NODE_HEIGHT = 100;

interface LayoutedElements {
  nodes: Node[];
  edges: Edge[];
}

async function getLayoutedElements(
  dagNodes: DagNodeView[],
  dagEdges: { id: string; source: string; target: string; relation: CardDepRelation }[]
): Promise<LayoutedElements> {
  const graph = {
    id: 'root',
    layoutOptions: elkOptions,
    children: dagNodes.map((node) => ({
      id: node.id,
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
    })),
    edges: dagEdges.map((edge) => ({
      id: edge.id,
      sources: [edge.target],  // Swap: dependency (target) is the source of the flow
      targets: [edge.source],  // Swap: dependent (source) is the target of the flow
    })),
  };

  const layoutedGraph = await elk.layout(graph);

  const nodes: Node[] = (layoutedGraph.children || []).map((node) => {
    const dagNode = dagNodes.find((n) => n.id === node.id)!;
    return {
      id: node.id,
      type: 'card',
      position: { x: node.x || 0, y: node.y || 0 },
      data: dagNode,
    };
  });

  const edges: Edge[] = dagEdges.map((edge) => ({
    id: edge.id,
    source: edge.target,  // Swap: flow from dependency to dependent
    target: edge.source,  // Swap: flow from dependency to dependent
    type: 'dependency',
    data: { relation: edge.relation },
    animated: edge.relation === CardDepRelation.PARALLEL_WITH,
  }));

  return { nodes, edges };
}

export default function DagPage() {
  const params = useParams();
  const router = useRouter();
  const projectSlug = params.slug as string;

  // Fetch DAG data
  const { data: dagData, isLoading, error } = useProjectDag(projectSlug);

  // React Flow state
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [isLayouting, setIsLayouting] = useState(false);
  const [hasLayouted, setHasLayouted] = useState(false);

  // Drawer state
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // Get selected node data
  const selectedNode = useMemo(() => {
    if (!selectedNodeId || !dagData) return null;
    return dagData.nodes.find((n) => n.id === selectedNodeId) || null;
  }, [selectedNodeId, dagData]);

  // Layout nodes when data loads
  useMemo(() => {
    if (dagData && !hasLayouted && !isLayouting) {
      setIsLayouting(true);
      getLayoutedElements(dagData.nodes, dagData.edges)
        .then(({ nodes: layoutedNodes, edges: layoutedEdges }) => {
          setNodes(layoutedNodes);
          setEdges(layoutedEdges);
          setHasLayouted(true);
        })
        .finally(() => {
          setIsLayouting(false);
        });
    }
  }, [dagData, hasLayouted, isLayouting, setNodes, setEdges]);

  // Handle node click
  const onNodeClick: NodeMouseHandler = useCallback((event, node) => {
    setSelectedNodeId(node.id);
  }, []);

  // Handle close drawer
  const handleCloseDrawer = useCallback(() => {
    setSelectedNodeId(null);
  }, []);

  // Handle edit card
  const handleEditCard = useCallback(() => {
    if (selectedNodeId) {
      router.push(`/projects/${projectSlug}/cards/${selectedNodeId}` as any);
    }
  }, [selectedNodeId, projectSlug, router]);

  if (isLoading || isLayouting) {
    return (
      <div className="flex h-[80vh] items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-muted-foreground">
            {isLayouting ? 'Calculating layout...' : 'Loading DAG...'}
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-[80vh] gap-4">
        <p className="text-muted-foreground">Failed to load DAG</p>
        <Button variant="outline" onClick={() => router.back()}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Go Back
        </Button>
      </div>
    );
  }

  if (!dagData || dagData.nodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-[80vh] gap-4">
        <Network className="h-16 w-16 text-muted-foreground" />
        <h2 className="text-xl font-semibold">No Cards Yet</h2>
        <p className="text-muted-foreground text-center max-w-md">
          Create cards in the backlog to see them visualized here as a dependency graph.
        </p>
        <Button onClick={() => router.push(`/projects/${projectSlug}/backlog` as any)}>
          Go to Backlog
        </Button>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-4rem)] w-full">
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
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
        <Controls />
        <MiniMap
          nodeStrokeWidth={3}
          zoomable
          pannable
          className="!bg-background/80"
        />
        <Panel position="top-left">
          <div className="flex items-center gap-4 bg-background/80 backdrop-blur p-2 rounded-lg border">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => router.push(`/projects/${projectSlug}` as any)}
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Project
            </Button>
            <div className="h-6 w-px bg-border" />
            <div className="text-sm text-muted-foreground">
              {dagData.nodes.length} cards · {dagData.edges.length} dependencies
            </div>
          </div>
        </Panel>
        <Panel position="bottom-left">
          <div className="flex items-center gap-4 bg-background/80 backdrop-blur p-2 rounded-lg border text-xs">
            <div className="flex items-center gap-2">
              <div className="w-8 h-0.5 bg-foreground" />
              <span>Depends On</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-8 h-0.5 border-t-2 border-dashed border-foreground" />
              <span>Parallel With</span>
            </div>
          </div>
        </Panel>
      </ReactFlow>

      <CardDrawer
        node={selectedNode}
        open={!!selectedNodeId}
        onClose={handleCloseDrawer}
        onEdit={handleEditCard}
      />
    </div>
  );
}
