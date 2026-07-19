import React, { forwardRef, useCallback, useState } from 'react'
import { ReactFlow, Background, Controls, MiniMap, Panel, useReactFlow } from '@xyflow/react'
import type { Node, Edge, Connection, ReactFlowInstance } from '@xyflow/react'
import { useLayoutStore, type LayoutDirection } from './layout-store'
import dagre from '@dagrejs/dagre'
import { Play, Trash2, Share2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { nodeTypes } from './nodes'
import WorkflowToolbar from './workflow-toolbar'
import WorkflowCallConfigPanel from './workflow-call-config-panel'
import { useTranslation } from '@/i18n'

interface WorkflowEditorProps {
  nodes: Node[]
  edges: Edge[]
  onNodesChange: any
  onEdgesChange: any
  onConnect: (connection: Connection) => void
  onNodeClick: (event: React.MouseEvent, node: Node) => void
  onDrop: (event: React.DragEvent<HTMLDivElement>) => void
  onDragOver: (event: React.DragEvent<HTMLDivElement>) => void
  onInit: (instance: any) => void
  selectedNode: Node | null
  deleteSelectedNode: () => void
  runWorkflow: () => void
  mutationDisabled?: boolean
  exportDisabled?: boolean
  // History controls.
  undoable?: boolean
  redoable?: boolean
  onUndo?: () => void
  onRedo?: () => void
  // Save/import/export handlers.
  onSave?: () => void
  onExport?: () => void
  onImport?: () => void
  // Layout callbacks.
  onNodesSet?: (nodes: Node[]) => void
  onEdgesSet?: (edges: Edge[]) => void
  leftPanel?: React.ReactNode
  rightPanel?: React.ReactNode
  // Workflow metadata.
  workflowId?: string
  workflowName?: string
}

// Defines the layout for nodes and edges.
const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = 'TB') => {
  const dagreGraph = new dagre.graphlib.Graph()
  dagreGraph.setDefaultEdgeLabel(() => ({}))

  const isHorizontal = direction === 'LR'

  dagreGraph.setGraph({
    rankdir: direction,
    nodesep: isHorizontal ? 50 : 80,
    ranksep: isHorizontal ? 150 : 100,
  })

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, {
      width: node.width || 172,
      height: node.height || 36,
    })
  })

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target)
  })

  dagre.layout(dagreGraph)

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id)

    return {
      ...node,
      position: {
        x: nodeWithPosition.x - (node.width || 172) / 2,
        y: nodeWithPosition.y - (node.height || 36) / 2,
      },
    }
  })

  return { nodes: layoutedNodes, edges }
}

const WorkflowEditor = forwardRef<HTMLDivElement, WorkflowEditorProps>(
  (
    {
      nodes,
      edges,
      onNodesChange,
      onEdgesChange,
      onConnect,
      onNodeClick,
      onDrop,
      onDragOver,
      onInit,
      selectedNode,
      deleteSelectedNode,
      runWorkflow,
      mutationDisabled = false,
      exportDisabled = false,
      undoable,
      redoable,
      onUndo,
      onRedo,
      onSave,
      onExport,
      onImport,
      onNodesSet,
      onEdgesSet,
      leftPanel,
      rightPanel,
      workflowId = '',
      workflowName = '',
    },
    ref
  ) => {
    const { t } = useTranslation()
    const { fitView, zoomIn, zoomOut } = useReactFlow()
    const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance | null>(null)
    const { setDirection } = useLayoutStore()
    const [showCallConfigPanel, setShowCallConfigPanel] = useState(false)
    const resolvedWorkflowName = workflowName || t('workflow.build.defaultName')

    const handleInit = (instance: ReactFlowInstance) => {
      setReactFlowInstance(instance)
      if (onInit) {
        onInit(instance)
      }
    }

    const handleZoomIn = () => {
      zoomIn()
    }

    const handleZoomOut = () => {
      zoomOut()
    }

    const handleResetView = () => {
      fitView({ padding: 0.2 })
    }

    const handleLayoutChange = useCallback(
      (direction: LayoutDirection) => {
        if (!reactFlowInstance) return

        setDirection(direction)

        const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(reactFlowInstance.getNodes(), reactFlowInstance.getEdges(), direction)

        if (onNodesSet) {
          onNodesSet(layoutedNodes)
        }

        if (onEdgesSet) {
          onEdgesSet(layoutedEdges)
        }

        window.requestAnimationFrame(() => {
          fitView({ padding: 0.2 })
        })
      },
      [reactFlowInstance, setDirection, onNodesSet, onEdgesSet, fitView]
    )

    const handleShowCallConfig = () => {
      setShowCallConfigPanel(true)
    }

    const handleCloseCallConfig = () => {
      setShowCallConfigPanel(false)
    }

    return (
      <div ref={ref} className="h-full w-full relative">
        <div className="h-full w-auto absolute left-0 top-0 z-10">{leftPanel}</div>
        <div className="h-full w-auto absolute right-0 top-0 z-10">{rightPanel}</div>

        <div className="h-full w-full">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onInit={handleInit}
            fitView
            nodeTypes={nodeTypes}
            proOptions={{ hideAttribution: true }}
            deleteKeyCode={['Backspace', 'Delete']}
            className="workflow-editor"
          >
            <Background />
            <Controls showInteractive={false} />
            <MiniMap />

            <Panel position="top-center" className="flex gap-2 p-2">
              <div className="flex items-center gap-2 bg-background/80 backdrop-blur-sm p-1 rounded-full shadow-sm">
                <TooltipProvider>
                  <Tooltip delayDuration={300}>
                    <TooltipTrigger asChild>
                      <Button
                        size="icon"
                        variant="default"
                        className="h-8 w-8 rounded-full"
                        aria-label={t('workflow.build.actions.testRun')}
                        disabled={mutationDisabled}
                        onClick={runWorkflow}
                      >
                        <Play className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="bottom">
                      <p>{t('workflow.build.actions.testRun')}</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>

                <TooltipProvider>
                  <Tooltip delayDuration={300}>
                    <TooltipTrigger asChild>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8 rounded-full"
                        aria-label={t('workflow.build.actions.callConfig')}
                        onClick={handleShowCallConfig}
                      >
                        <Share2 className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="bottom">
                      <p>{t('workflow.build.actions.callConfig')}</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>

                {selectedNode && (
                  <TooltipProvider>
                    <Tooltip delayDuration={300}>
                      <TooltipTrigger asChild>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-8 w-8 rounded-full text-destructive hover:text-destructive hover:bg-destructive/10"
                          aria-label={t('workflow.build.actions.deleteSelected')}
                          disabled={selectedNode.type === 'compatibility-node'}
                          onClick={deleteSelectedNode}
                        >
                          <Trash2 className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="bottom">
                      <p>{t('workflow.build.actions.deleteSelected')}</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}
            </div>
          </Panel>

            <WorkflowToolbar
              flowInstance={reactFlowInstance}
              onZoomIn={handleZoomIn}
              onZoomOut={handleZoomOut}
              onResetView={handleResetView}
              onUndo={onUndo || (() => {})}
              onRedo={onRedo || (() => {})}
              onSave={onSave || (() => {})}
              onExport={onExport || (() => {})}
              onImport={onImport || (() => {})}
              getLayoutedElements={getLayoutedElements}
              undoable={undoable || false}
              redoable={redoable || false}
              saveDisabled={mutationDisabled}
              exportDisabled={exportDisabled}
            />
          </ReactFlow>
        </div>

        <WorkflowCallConfigPanel
          workflowId={workflowId}
          workflowName={resolvedWorkflowName}
          visible={showCallConfigPanel}
          onClose={handleCloseCallConfig}
        />
      </div>
    )
  }
)

export default WorkflowEditor
