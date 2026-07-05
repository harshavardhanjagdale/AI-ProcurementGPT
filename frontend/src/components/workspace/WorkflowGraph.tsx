'use client';

import { useCallback, useEffect, useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  Position,
  MarkerType,
  type Node,
  type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { cn } from '@/lib/utils';
import type { WorkflowStep } from '@/services/workflow.service';

interface WorkflowGraphProps {
  steps: WorkflowStep[];
  currentStep: string | null;
  currentAgent: string | null;
  progress: number;
}

function WorkflowNode({ data }: { data: any }) {
  const { label, status, agent, isActive } = data;

  const statusStyles: Record<string, string> = {
    completed: 'bg-green-50 border-green-400 text-green-800',
    running: 'bg-blue-50 border-blue-500 text-blue-800 shadow-lg shadow-blue-100',
    failed: 'bg-red-50 border-red-400 text-red-800',
    pending: 'bg-gray-50 border-gray-300 text-gray-500',
    skipped: 'bg-gray-50 border-gray-200 text-gray-400',
  };

  const statusIcons: Record<string, string> = {
    completed: '✓',
    running: '●',
    failed: '✗',
    pending: '○',
    skipped: '–',
  };

  return (
    <div
      className={cn(
        'px-4 py-3 rounded-xl border-2 min-w-[160px] transition-all duration-300',
        statusStyles[status] || statusStyles.pending,
        isActive && 'animate-pulse ring-2 ring-blue-400 ring-offset-2'
      )}
    >
      <div className="flex items-center gap-2">
        <span
          className={cn(
            'w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold',
            status === 'completed' && 'bg-green-500 text-white',
            status === 'running' && 'bg-blue-500 text-white',
            status === 'failed' && 'bg-red-500 text-white',
            status === 'pending' && 'bg-gray-300 text-gray-600',
          )}
        >
          {statusIcons[status] || '○'}
        </span>
        <span className="text-sm font-semibold">{label}</span>
      </div>
      {agent && (
        <p className="text-[10px] mt-1 ml-7 opacity-75">{agent}</p>
      )}
    </div>
  );
}

const nodeTypes = { workflowNode: WorkflowNode };

export function WorkflowGraph({ steps, currentStep, currentAgent, progress }: WorkflowGraphProps) {
  const buildGraph = useCallback(() => {
    const nodes: Node[] = steps.map((step, index) => ({
      id: step.name,
      type: 'workflowNode',
      position: { x: 50, y: index * 80 },
      data: {
        label: step.display_name,
        status: step.status,
        agent: step.agent,
        isActive: step.name === currentStep,
      },
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
    }));

    const edges: Edge[] = steps.slice(0, -1).map((step, index) => ({
      id: `${step.name}-${steps[index + 1].name}`,
      source: step.name,
      target: steps[index + 1].name,
      animated: step.status === 'running' || steps[index + 1].status === 'running',
      style: {
        stroke:
          step.status === 'completed'
            ? '#22c55e'
            : step.status === 'running'
              ? '#3b82f6'
              : '#d1d5db',
        strokeWidth: 2,
      },
      markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12 },
    }));

    return { nodes, edges };
  }, [steps, currentStep]);

  const { nodes: initialNodes, edges: initialEdges } = buildGraph();
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    const { nodes: newNodes, edges: newEdges } = buildGraph();
    setNodes(newNodes);
    setEdges(newEdges);
  }, [steps, currentStep, buildGraph, setNodes, setEdges]);

  if (steps.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-gray-400 text-sm">
        Workflow will appear here once started
      </div>
    );
  }

  return (
    <div className="h-full w-full">
      {/* Stats Bar */}
      <div className="px-4 py-3 border-b border-gray-200 bg-white">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-gray-900">Procurement Workflow</h3>
          <span className="text-xs text-gray-500">{Math.round(progress)}%</span>
        </div>
        <div className="w-full h-1.5 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-600 rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
        {currentAgent && (
          <div className="mt-2 flex items-center gap-2">
            <span className="text-[10px] px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full font-medium">
              {currentAgent}
            </span>
            {currentStep && (
              <span className="text-[10px] text-gray-500">
                {steps.find(s => s.name === currentStep)?.display_name}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Flow Graph */}
      <div className="h-[calc(100%-80px)]">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          proOptions={{ hideAttribution: true }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnDrag
          zoomOnScroll
        >
          <Background color="#f1f5f9" gap={20} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </div>
  );
}
