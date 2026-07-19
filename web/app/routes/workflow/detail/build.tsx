import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react'
import { useTranslation } from '@/i18n'
import { useParams } from 'react-router'
import { useNavigate } from '@/hooks/use-navigate'
import { useNodesState, useEdgesState, addEdge, ReactFlowProvider } from '@xyflow/react'
import type { Node, Edge, Connection, NodeChange, EdgeChange } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Separator } from '@/components/ui/separator'
import { toast } from 'sonner'
import useDialog from '@/hooks/use-dialog'
import {
  createTicketTriageWorkflow,
  createWorkflowVersion,
  getCurrentWorkflowVersion,
  getWorkflow,
  updateWorkflow,
} from '@/services/workflow-service'

// Import node types and metadata.
import { getDefaultNodeData } from './ui/build/nodes'
import { isCanonicalBuilderType, type CanonicalBuilderType } from './ui/build/canonical-node-registry'

// Import custom components.
import WorkflowInfoPanel from './ui/build/workflow-info-panel'
import NodeLibraryPanel from './ui/build/node-library-panel'
import NodePropertiesPanel from './ui/build/node-properties-panel'
import WorkflowEditor from './ui/build/workflow-editor'
import { Card, CardContent } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  CanonicalNodeValidationError,
  isWorkflowSpecImportStructure,
  parseWorkflowVersion,
  serializeWorkflowSpec,
  serializeWorkflowSpecForExport,
  UnsupportedBuilderNodeError,
  UnsupportedWorkflowEdgeError,
  type WorkflowSpecBase,
} from './ui/build/workflow-spec'

interface BuildPageProps { }

const newWorkflowBase = (): WorkflowSpecBase => ({
  inputs_schema: { type: 'object', properties: {} },
  outputs_schema: { type: 'object', properties: {} },
})

const BuildPage: React.FC<BuildPageProps> = () => {
  const { t } = useTranslation()
  const { id } = useParams()
  const navigate = useNavigate()
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const [reactFlowInstance, setReactFlowInstance] = useState<any>(null)
  const [pageLoading, setPageLoading] = useState(false)
  const [savingWorkflow, setSavingWorkflow] = useState(false)
  const [creatingTemplate, setCreatingTemplate] = useState(false)
  const [capabilityMutationBlocked, setCapabilityMutationBlocked] = useState(true)

  // State management.
  const [workflowName, setWorkflowName] = useState(() => t('workflow.detail.build.defaultName'))
  const [workflowDescription, setWorkflowDescription] = useState('')
  const [workflowBase, setWorkflowBase] = useState<WorkflowSpecBase>(newWorkflowBase)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [invalidDraftNodeIds, setInvalidDraftNodeIds] = useState<Set<string>>(() => new Set())

  // History state.
  const [history, setHistory] = useState<{ nodes: Node[][], edges: Edge[][], currentIndex: number }>({
    nodes: [],
    edges: [],
    currentIndex: -1,
  })
  const [undoable, setUndoable] = useState(false)
  const [redoable, setRedoable] = useState(false)

  // Track undo/redo operations.
  const isHistoryActionRef = useRef(false)

  // Dialog handler.
  const dialog = useDialog()
  const DialogComponent = dialog.DialogComponent

  // Initial nodes and edges.
  const initialNodes = useMemo<Node[]>(() => [
    {
      id: 'transform-1',
      type: 'transform-node',
      position: { x: 100, y: 100 },
      data: {
        ...getDefaultNodeData('transform-node'),
        label: t('workflow.detail.nodes.transform.label'),
        mapping: { value: '{{ inputs }}' },
      },
    },
    {
      id: 'output-1',
      type: 'output-node',
      position: { x: 400, y: 100 },
      data: {
        ...getDefaultNodeData('output-node'),
        label: t('workflow.detail.nodes.output.label'),
        value: '{{ steps.transform-1.output.value }}',
      },
    },
  ], [t])

  const initialEdges = useMemo<Edge[]>(() => [
    { id: 'e1-2', source: 'transform-1', target: 'output-1' },
  ], [])

  const seedHistory = useCallback((nextNodes: Node[], nextEdges: Edge[]) => {
    setHistory({
      nodes: [[...nextNodes]],
      edges: [[...nextEdges]],
      currentIndex: 0,
    })
    setUndoable(false)
    setRedoable(false)
  }, [])

  // ReactFlow state hooks.
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)
  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selectedNodeId) ?? null,
    [nodes, selectedNodeId],
  )
  const hasCompatibilityNodes = useMemo(
    () => nodes.some((node) => node.type === 'compatibility-node'),
    [nodes],
  )
  const hasUnsupportedEdges = useMemo(
    () => edges.some((edge) => edge.data?.unsupported === true),
    [edges],
  )
  const hasInvalidDrafts = invalidDraftNodeIds.size > 0
  const mutationDisabled = hasCompatibilityNodes || hasUnsupportedEdges || hasInvalidDrafts
  const handleCapabilityMutationBlocked = useCallback((blocked: boolean) => {
    setCapabilityMutationBlocked(blocked)
  }, [])
  const handleNodeValidityChange = useCallback((nodeId: string, valid: boolean) => {
    setInvalidDraftNodeIds((current) => {
      const next = new Set(current)
      if (valid) next.delete(nodeId)
      else next.add(nodeId)
      return next
    })
  }, [])

  // Custom node change handler for history.
  const handleNodesChange = useCallback(
    (changes: NodeChange[]) => {
      if (!isHistoryActionRef.current) {
        // Record history only for non-undo/redo actions.
        addToHistory()
      }
      onNodesChange(changes)
    },
    [nodes, edges, onNodesChange]
  )

  // Custom edge change handler for history.
  const handleEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      if (!isHistoryActionRef.current) {
        // Record history only for non-undo/redo actions.
        addToHistory()
      }
      onEdgesChange(changes)
    },
    [nodes, edges, onEdgesChange]
  )

  // Handle direct node set (layout switching).
  const handleNodesSet = useCallback(
    (newNodes: Node[]) => {
      // Record history.
      if (!isHistoryActionRef.current) {
        addToHistory()
      }
      setNodes(newNodes)
    },
    [setNodes]
  )

  // Handle direct edge set (layout switching).
  const handleEdgesSet = useCallback(
    (newEdges: Edge[]) => {
      setEdges(newEdges)
    },
    [setEdges]
  )

  // Handle connection.
  const onConnect = useCallback(
    (connection: Connection) => {
      if (!isHistoryActionRef.current) {
        // Record history.
        addToHistory()
      }
      setEdges((eds) => addEdge(connection, eds))
    },
    [setEdges]
  )

  // Handle node drag over.
  const onDragOver = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  // Handle node drop.
  const onDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault()

      const reactFlowBounds = reactFlowWrapper.current?.getBoundingClientRect()
      if (!reactFlowBounds || !reactFlowInstance || capabilityMutationBlocked) return

      const type = event.dataTransfer.getData('application/reactflow/type')
      const label = event.dataTransfer.getData('application/reactflow/label')

      // Validate node type.
      if (!isCanonicalBuilderType(type)) return

      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX - reactFlowBounds.left,
        y: event.clientY - reactFlowBounds.top,
      })

      const newNode: Node = {
        id: `${type}-${Date.now()}`,
        type,
        position,
        data: { ...getDefaultNodeData(type), label },
      }

      // Record history.
      addToHistory()
      setNodes((nds) => nds.concat(newNode))
    },
    [capabilityMutationBlocked, reactFlowInstance, setNodes]
  )

  // Handle node click.
  const onNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    setSelectedNodeId(node.id)
  }, [])

  // Handle save.
  const handleSave = useCallback(() => {
    if (!workflowName.trim()) {
      toast.error(t('workflow.detail.build.toast.nameRequired'))
      return
    }

    // Persist workflow.
    const workflow = {
      id: id || Date.now().toString(),
      name: workflowName,
      description: workflowDescription,
      nodes,
      edges,
    }

    toast.success(t('workflow.detail.build.toast.saved'))
  }, [id, workflowName, workflowDescription, nodes, edges, t])

  // Handle node drag start.
  const onDragStart = (event: React.DragEvent<HTMLElement>, nodeType: string, nodeLabel: string) => {
    event.dataTransfer.setData('application/reactflow/type', nodeType)
    event.dataTransfer.setData('application/reactflow/label', nodeLabel)
    event.dataTransfer.effectAllowed = 'move'
  }

  // Add new node.
  const addNewNode = (type: CanonicalBuilderType, label: string) => {
    if (capabilityMutationBlocked) return
    const newNode: Node = {
      id: `${type}-${Date.now()}`,
      type,
      position: {
        x: Math.random() * 300 + 50,
        y: Math.random() * 300 + 50,
      },
      data: { ...getDefaultNodeData(type), label },
    }

    // Record history.
    addToHistory()
    setNodes((nds) => nds.concat(newNode))
  }

  // Update node data.
  const updateNodeData = (nodeId: string, newData: any) => {
    // Record history.
    addToHistory()
    setNodes((nds) =>
      nds.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, ...newData } } : n))
    )
  }

  // Delete selected node.
  const deleteSelectedNode = () => {
    if (selectedNode && selectedNode.type !== 'compatibility-node') {
      // Record history.
      addToHistory()
      setNodes((nds) => nds.filter((node) => node.id !== selectedNode.id))
      setEdges((eds) => eds.filter(
        (edge) => edge.source !== selectedNode.id && edge.target !== selectedNode.id
      ))
      setSelectedNodeId(null)
    }
  }

  // Run workflow.
  const runWorkflow = () => {
    if (mutationDisabled) return
    toast.info(t('workflow.detail.build.toast.running'))
    // Execute workflow run here.
  }

  // Append history entry.
  const addToHistory = () => {
    if (isHistoryActionRef.current) return

    setHistory(prev => {
      // Drop history after the current index when diverging.
      const newNodes = [...prev.nodes.slice(0, prev.currentIndex + 1), [...nodes]]
      const newEdges = [...prev.edges.slice(0, prev.currentIndex + 1), [...edges]]
      const newIndex = prev.currentIndex + 1

      // Update undo/redo state.
      setUndoable(newIndex > 0)
      setRedoable(false)

      return {
        nodes: newNodes,
        edges: newEdges,
        currentIndex: newIndex,
      }
    })
  }

  // Undo action.
  const handleUndo = useCallback(() => {
    setHistory(prev => {
      if (prev.currentIndex <= 0) return prev

      const newIndex = prev.currentIndex - 1
      const prevNodes = prev.nodes[newIndex]
      const prevEdges = prev.edges[newIndex]

      // Mark as history action to avoid duplicates.
      isHistoryActionRef.current = true
      setNodes(prevNodes)
      setEdges(prevEdges)

      // Update undo/redo state.
      setUndoable(newIndex > 0)
      setRedoable(true)

      // Reset history action flag.
      setTimeout(() => {
        isHistoryActionRef.current = false
      }, 0)

      return {
        ...prev,
        currentIndex: newIndex,
      }
    })
  }, [])

  // Redo action.
  const handleRedo = useCallback(() => {
    setHistory(prev => {
      if (prev.currentIndex >= prev.nodes.length - 1) return prev

      const newIndex = prev.currentIndex + 1
      const nextNodes = prev.nodes[newIndex]
      const nextEdges = prev.edges[newIndex]

      // Mark as history action to avoid duplicates.
      isHistoryActionRef.current = true
      setNodes(nextNodes)
      setEdges(nextEdges)

      // Update undo/redo state.
      setUndoable(true)
      setRedoable(newIndex < prev.nodes.length - 1)

      // Reset history action flag.
      setTimeout(() => {
        isHistoryActionRef.current = false
      }, 0)

      return {
        ...prev,
        currentIndex: newIndex,
      }
    })
  }, [])

  const loadWorkflow = useCallback(async () => {
    if (!id) {
      setWorkflowBase(newWorkflowBase())
      seedHistory(initialNodes, initialEdges)
      return
    }

    try {
      setPageLoading(true)
      const [workflow, currentVersion] = await Promise.all([
        getWorkflow(id),
        getCurrentWorkflowVersion(id).catch(() => null),
      ])

      setWorkflowName(workflow.name || t('workflow.detail.build.defaultName'))
      setWorkflowDescription(workflow.description || '')

      if (currentVersion) {
        const restoredGraph = parseWorkflowVersion(currentVersion)
        setInvalidDraftNodeIds(new Set())
        setSelectedNodeId(null)
        setWorkflowBase(restoredGraph.base)
        setNodes(restoredGraph.nodes)
        setEdges(restoredGraph.edges)
        if (restoredGraph.name) {
          setWorkflowName(restoredGraph.name)
        }
        if (restoredGraph.description) {
          setWorkflowDescription(restoredGraph.description)
        }
        if (restoredGraph.nodes.length) {
          seedHistory(restoredGraph.nodes, restoredGraph.edges)
          return
        }
        setNodes(initialNodes)
        setEdges(initialEdges)
        seedHistory(initialNodes, initialEdges)
        return
      }

      setWorkflowBase(newWorkflowBase())
      setInvalidDraftNodeIds(new Set())
      setSelectedNodeId(null)
      setNodes(initialNodes)
      setEdges(initialEdges)
      seedHistory(initialNodes, initialEdges)
    } catch (error) {
      toast.error('Failed to load workflow builder state.')
      console.error('Failed to load workflow builder state:', error)
      setWorkflowBase(newWorkflowBase())
      setInvalidDraftNodeIds(new Set())
      setSelectedNodeId(null)
      setNodes(initialNodes)
      setEdges(initialEdges)
      seedHistory(initialNodes, initialEdges)
    } finally {
      setPageLoading(false)
    }
  }, [id, initialEdges, initialNodes, seedHistory, setEdges, setNodes, t])

  // Save workflow.
  const handleSaveWorkflow = useCallback(async () => {
    if (mutationDisabled) return
    if (!workflowName.trim()) {
      toast.error(t('workflow.detail.build.toast.nameRequired'))
      return
    }

    if (!id) {
      toast.error('Workflow ID is missing.')
      return
    }

    try {
      setSavingWorkflow(true)
      const spec = serializeWorkflowSpec(
        workflowBase,
        workflowName.trim(),
        workflowDescription.trim(),
        nodes,
        edges
      )

      await createWorkflowVersion(id, {
        graph_json: spec,
      })
      try {
        await updateWorkflow(id, {
          name: workflowName.trim(),
          description: workflowDescription.trim() || undefined,
        })
      } catch (metadataError) {
        toast.error('Workflow version saved, but workflow metadata update failed.')
        console.error('Workflow version saved but metadata update failed:', metadataError)
        await loadWorkflow()
        return
      }
      toast.success(t('workflow.detail.build.toast.saved'))
      await loadWorkflow()
    } catch (error) {
      const message = error instanceof CanonicalNodeValidationError
        || error instanceof UnsupportedBuilderNodeError
        || error instanceof UnsupportedWorkflowEdgeError
        ? error.message
        : 'Failed to save workflow version.'
      toast.error(message)
      console.error('Failed to save workflow version:', error)
    } finally {
      setSavingWorkflow(false)
    }
  }, [id, loadWorkflow, mutationDisabled, nodes, edges, t, workflowBase, workflowDescription, workflowName])

  // Export workflow.
  const handleExportWorkflow = useCallback(() => {
    if (hasInvalidDrafts) {
      toast.error(t('workflow.detail.build.export.invalidDraft'))
      return
    }
    if (!workflowName.trim()) {
      toast.error(t('workflow.detail.build.toast.nameRequired'))
      return
    }

    try {
      const graphJson = serializeWorkflowSpecForExport(
        workflowBase,
        workflowName.trim(),
        workflowDescription.trim(),
        nodes,
        edges,
      )
      const workflowData = {
        format: 'soit-workflow-spec-v1',
        graph_json: graphJson,
        exported_at: new Date().toISOString(),
      }
      const dataStr = JSON.stringify(workflowData, null, 2)
      const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr)
      const exportFileName = `${workflowName.replace(/\s+/g, '_')}_${new Date().getTime()}.json`
      const linkElement = document.createElement('a')
      linkElement.setAttribute('href', dataUri)
      linkElement.setAttribute('download', exportFileName)
      linkElement.click()
      toast.success(t('workflow.detail.build.toast.exported'))
    } catch (error) {
      const message = error instanceof Error ? error.message : t('workflow.detail.build.import.invalidData')
      toast.error(message)
    }
  }, [edges, hasInvalidDrafts, nodes, t, workflowBase, workflowDescription, workflowName])

  // Import workflow.
  const handleImportWorkflow = useCallback(() => {
    // Create file input.
    const fileInput = document.createElement('input')
    fileInput.type = 'file'
    fileInput.accept = '.json'

    fileInput.onchange = (e: Event) => {
      const target = e.target as HTMLInputElement
      if (!target.files || target.files.length === 0) return

      const file = target.files[0]
      const reader = new FileReader()

      reader.onload = (event) => {
        try {
          const result = event.target?.result
          if (typeof result !== 'string') return

          const workflowData = JSON.parse(result) as Record<string, unknown>

          // Validate imported data.
          if (
            workflowData.format !== 'soit-workflow-spec-v1'
            || !isWorkflowSpecImportStructure(workflowData.graph_json)
          ) {
            throw new Error(t('workflow.detail.build.import.invalidData'))
          }
          const restoredGraph = parseWorkflowVersion({
            graph_json: workflowData.graph_json,
          })
          if (!restoredGraph.nodes.length) {
            throw new Error(t('workflow.detail.build.import.invalidData'))
          }

          const importedName = restoredGraph.name || t('workflow.detail.build.import.unnamed')

          // Confirm import.
          dialog.confirm({
            title: t('workflow.detail.build.import.title'),
            description: t('workflow.detail.build.import.confirmDescription', { name: importedName }),
            confirmText: t('workflow.detail.build.import.confirm'),
            cancelText: t('workflow.detail.build.import.cancel'),
            onConfirm: () => {
              // Record history.
              addToHistory()

              // Update workflow data.
              setWorkflowName(restoredGraph.name || t('workflow.detail.build.import.importedFallbackName'))
              setWorkflowDescription(restoredGraph.description)
              setWorkflowBase(restoredGraph.base)
              setNodes(restoredGraph.nodes)
              setEdges(restoredGraph.edges)
              setInvalidDraftNodeIds(new Set())
              setSelectedNodeId(null)

              toast.success(t('workflow.detail.build.toast.imported'))
            },
          })
        } catch (error) {
          console.error('Failed to import workflow:', error)
          toast.error(t('workflow.detail.build.import.invalidFile'))
        }
      }

      reader.readAsText(file)
    }

    fileInput.click()
  }, [dialog, setEdges, setNodes, t])

  const handleCreateTicketTemplate = useCallback(async () => {
    try {
      setCreatingTemplate(true)
      const workflow = await createTicketTriageWorkflow({ name: 'Ticket triage' })
      toast.success(t('workflow.nodeLibrary.templates.ticketTriage.created'))
      navigate(`/workflow/${workflow.id}/build`)
    } catch (error) {
      toast.error(t('workflow.nodeLibrary.templates.ticketTriage.createError'))
      console.error('Failed to create ticket triage workflow:', error)
    } finally {
      setCreatingTemplate(false)
    }
  }, [navigate, t])

  useEffect(() => {
    loadWorkflow()
  }, [loadWorkflow])

  const renderLeftPanel = () => {
    return (
      <div className="w-80 m-0 mb-2 p-2 bg-background flex flex-col h-full">
        <Card className="w-full h-full shadow-none border-1 rounded-lg">
          <CardContent className="px-2 h-full overflow-hidden">
            <WorkflowInfoPanel
              workflowName={workflowName}
              workflowDescription={workflowDescription}
              setWorkflowName={setWorkflowName}
              setWorkflowDescription={setWorkflowDescription}
            />

            <Separator className="my-4" />

            <div className="flex flex-col h-full">
              <ScrollArea className="h-full">
                <NodeLibraryPanel
                  onDragStart={onDragStart}
                  addNewNode={addNewNode}
                  onCreateTicketTemplate={handleCreateTicketTemplate}
                  creatingTicketTemplate={creatingTemplate}
                  onMutationBlockedChange={handleCapabilityMutationBlocked}
                />
              </ScrollArea>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  const renderRightPanel = () => {
    return (
      <div className="w-100 m-0 mb-2 p-2 bg-background flex flex-col h-full">
        <NodePropertiesPanel
          selectedNode={selectedNode}
          updateNodeData={updateNodeData}
          onNodeValidityChange={handleNodeValidityChange}
          className="border-1 rounded-lg px-2"
        />
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col h-full w-full">
      {(hasCompatibilityNodes || hasUnsupportedEdges) && (
        <div role="alert" className="mx-2 mb-1 rounded-md border border-amber-500/50 bg-amber-500/10 px-3 py-2 text-sm">
          {hasCompatibilityNodes
            ? t('workflow.detail.build.compatibilityMessage')
            : t('workflow.detail.build.unsupportedEdgeMessage')}
        </div>
      )}
      <div className="flex flex-1 overflow-hidden h-full">
        <div className="flex flex-1 overflow-hidden h-full">
          <ReactFlowProvider>
            <WorkflowEditor
              ref={reactFlowWrapper}
              leftPanel={renderLeftPanel()}
              rightPanel={renderRightPanel()}
              nodes={nodes}
              edges={edges}
              onNodesChange={handleNodesChange}
              onEdgesChange={handleEdgesChange}
              onConnect={onConnect}
              onInit={setReactFlowInstance}
              onDrop={onDrop}
              onDragOver={onDragOver}
              onNodeClick={onNodeClick}
              selectedNode={selectedNode}
              deleteSelectedNode={deleteSelectedNode}
              runWorkflow={runWorkflow}
              mutationDisabled={mutationDisabled}
              exportDisabled={hasInvalidDrafts}
              undoable={undoable}
              redoable={redoable}
              onUndo={handleUndo}
              onRedo={handleRedo}
              onSave={handleSaveWorkflow}
              onExport={handleExportWorkflow}
              onImport={handleImportWorkflow}
              onNodesSet={handleNodesSet}
              onEdgesSet={handleEdgesSet}
              workflowId={id || ''}
              workflowName={workflowName}
            />
          </ReactFlowProvider>
        </div>
      </div>
      <DialogComponent />
    </div>
  )
}

export default BuildPage
