'use client';

import { memo } from 'react';
import { EdgeProps, getBezierPath, EdgeLabelRenderer } from 'reactflow';
import { cn } from '@/lib/utils';
import { FlowRelationshipType } from '@/lib/api/types';

// Edge data type
export interface DependencyEdgeData {
  label?: string;
  relationshipType: FlowRelationshipType;
  isConfirmed?: boolean;
  isRejected?: boolean;
}

// Relationship type styles
const relationshipStyles: Record<FlowRelationshipType, { color: string; strokeDasharray?: string }> = {
  [FlowRelationshipType.DATA_FLOW]: { color: '#3b82f6' }, // blue
  [FlowRelationshipType.CONTROL]: { color: '#8b5cf6', strokeDasharray: '5 5' }, // purple dashed
  [FlowRelationshipType.INFERRED]: { color: '#9ca3af', strokeDasharray: '3 3' }, // gray dashed
};

function DependencyEdgeComponent({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  data,
  markerEnd,
  selected,
}: EdgeProps<DependencyEdgeData>) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const relationshipStyle = data?.relationshipType 
    ? relationshipStyles[data.relationshipType] 
    : relationshipStyles[FlowRelationshipType.DATA_FLOW];

  const isConfirmed = data?.isConfirmed ?? false;
  const isRejected = data?.isRejected ?? false;

  // Adjust opacity for rejected edges
  const opacity = isRejected ? 0.3 : 1;
  const strokeWidth = selected ? 3 : isConfirmed ? 2 : 1.5;

  return (
    <>
      <path
        id={id}
        className="react-flow__edge-path"
        d={edgePath}
        strokeWidth={strokeWidth}
        stroke={relationshipStyle.color}
        strokeDasharray={relationshipStyle.strokeDasharray}
        style={{ ...style, opacity }}
        markerEnd={markerEnd}
      />
      {data?.label && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              pointerEvents: 'all',
            }}
            className={cn(
              'px-1.5 py-0.5 rounded text-[10px] font-mono',
              'bg-background border shadow-sm',
              isRejected && 'line-through opacity-50',
              isConfirmed && 'ring-1 ring-green-500'
            )}
          >
            {data.label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

export const DependencyEdge = memo(DependencyEdgeComponent);
