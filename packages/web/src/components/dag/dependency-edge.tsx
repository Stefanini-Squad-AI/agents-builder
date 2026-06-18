'use client';

import { memo } from 'react';
import { EdgeProps, getBezierPath, EdgeLabelRenderer } from 'reactflow';
import { CardDepRelation } from '@/lib/api/types';

interface DependencyEdgeData {
  relation: CardDepRelation;
}

function DependencyEdgeComponent({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
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

  const isParallel = data?.relation === CardDepRelation.PARALLEL_WITH;

  return (
    <>
      <path
        id={id}
        className={`react-flow__edge-path transition-all ${
          selected ? 'stroke-primary' : 'stroke-foreground/40'
        }`}
        d={edgePath}
        strokeWidth={selected ? 3 : 2}
        strokeDasharray={isParallel ? '8 4' : undefined}
        fill="none"
        markerEnd={isParallel ? undefined : 'url(#arrow)'}
      />
      {/* Arrow marker definition */}
      <defs>
        <marker
          id="arrow"
          viewBox="0 0 10 10"
          refX="8"
          refY="5"
          markerWidth="6"
          markerHeight="6"
          orient="auto-start-reverse"
        >
          <path
            d="M 0 0 L 10 5 L 0 10 z"
            className={selected ? 'fill-primary' : 'fill-foreground/40'}
          />
        </marker>
      </defs>
    </>
  );
}

export const DependencyEdge = memo(DependencyEdgeComponent);
