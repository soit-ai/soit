import type React from 'react'
import { useState, useCallback, useRef, useEffect, useMemo } from 'react'
import { useTranslation } from '@/i18n'
import { useNodesState, useEdgesState, addEdge } from '@xyflow/react'
import type { Node, Edge, Connection, NodeChange, EdgeChange } from '@xyflow/react'
import { toast } from 'sonner'
import useDialog from '@/hooks/use-dialog'
import {
  createTicketTriageWorkflow,
  createWorkflowVersion,
  getCurrentWorkflowVersionOrNull,
  getWorkflow,
  previewWorkflowVersion,
  updateWorkflow,
} from '@/services/workflow-service'

import { getDefaultNodeData } from '@/routes/workflow/detail/ui/build/nodes'
import {
  isCanonicalBuilderType,
  type CanonicalBuilderType,
} from '@/routes/workflow/detail/ui/build/canonical-node-registry'
import {
  CanonicalNodeValidationError,
  isWorkflowSpecImportStructure,
  parseWorkflowVersion,
  serializeWorkflowSpec,
  serializeWorkflowSpecForExport,
  UnsupportedBuilderNodeError,
  UnsupportedWorkflowEdgeError,
  type WorkflowSpecBase,
} from '@/routes/workflow/detail/ui/build/workflow-spec'

type BuilderOperation = {
  generation: number
  workflowId: string
}

/**
 * Route-shaped navigation the builder needs after an operation completes. The
 * legacy page points these at `/workflow/...` and `/observe/...`; the console
 * (v2) page points them at the `/v2/...` equivalents. Everything else about the
 * builder is identical between the two hosts.
 */
export interface WorkflowBuilderNavigation {
  /** Called with the run id produced by a successful test run. */
  toRun: (runId: string) => void
  /** Called with the id of a workflow created from a template. */
  toWorkflowBuild: (workflowId: string) => void
}

export interface UseWorkflowBuilderOptions {
  /** The workflow being edited. `undefined` keeps the builder unhydrated. */
  workflowId: string | undefined
  navigation: WorkflowBuilderNavigation
}

const newWorkflowBase = (): WorkflowSpecBase => ({
  inputs_schema: { type: 'object', properties: {} },
  outputs_schema: { type: 'object', properties: {} },
})

/**
 * The whole workflow-builder orchestration: graph state, history, drag/drop,
 * node mutation, load/save/import/export and test-run. Extracted verbatim from
 * `app/routes/workflow/detail/build.tsx` so the legacy page and the console (v2)
 * Build tab render one implementation with one set of behaviours.
 */
export function useWorkflowBuilder({ workflowId: id, navigation }: UseWorkflowBuilderOptions) {
  const { t } = useTranslation()
  const navigationRef = useRef(navigation)
  navigationRef.current = navigation
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const [reactFlowInstance, setReactFlowInstance] = useState<any>(null)
  const [pageLoading, setPageLoading] = useState(false)
  const [hydratedWorkflowId, setHydratedWorkflowId] = useState<string | null>(null)
  const [savingWorkflow, setSavingWorkflow] = useState(false)
  const [executingWorkflow, setExecutingWorkflow] = useState(false)
  const [creatingTemplate, setCreatingTemplate] = useState(false)
  const [importDialogContext, setImportDialogContext] = useState<BuilderOperation | null>(null)
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
  const operationLockRef = useRef(false)
  const operationGenerationRef = useRef(0)
  const loadRequestSequenceRef = useRef(0)
  const mountedRef = useRef(false)
  const currentWorkflowIdRef = useRef(id)
  const hydratedWorkflowIdRef = useRef<string | null>(null)
  const pageLoadingRef = useRef(pageLoading)
  currentWorkflowIdRef.current = id
  hydratedWorkflowIdRef.current = hydratedWorkflowId
  pageLoadingRef.current = pageLoading
  const operationBusy = savingWorkflow || executingWorkflow || creatingTemplate
  const builderHydrated = Boolean(id && hydratedWorkflowId === id)
  const builderInteractionDisabled = operationBusy || pageLoading || !builderHydrated
  const setWorkflowHydration = useCallback((workflowId: string | null) => {
    hydratedWorkflowIdRef.current = workflowId
    setHydratedWorkflowId(workflowId)
  }, [])
  const isCurrentWorkflowHydrated = useCallback((workflowId: string | undefined) => {
    return Boolean(
      mountedRef.current
      && workflowId
      && currentWorkflowIdRef.current === workflowId
      && hydratedWorkflowIdRef.current === workflowId
      && !pageLoadingRef.current
    )
  }, [])
  const isBuilderMutationBlocked = useCallback(() => {
    return operationLockRef.current
      || !isCurrentWorkflowHydrated(currentWorkflowIdRef.current)
  }, [isCurrentWorkflowHydrated])
  const isBuilderOperationActive = useCallback((operation: BuilderOperation) => {
    return mountedRef.current
      && operationGenerationRef.current === operation.generation
      && currentWorkflowIdRef.current === operation.workflowId
  }, [])
  const beginBuilderOperation = useCallback((workflowId: string | undefined) => {
    if (!workflowId || !isCurrentWorkflowHydrated(workflowId)) return null
    return {
      generation: ++operationGenerationRef.current,
      workflowId,
    } satisfies BuilderOperation
  }, [isCurrentWorkflowHydrated])
  const isBuilderImportContextActive = useCallback((context: BuilderOperation) => {
    return isBuilderOperationActive(context)
      && isCurrentWorkflowHydrated(context.workflowId)
  }, [isBuilderOperationActive, isCurrentWorkflowHydrated])

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      operationGenerationRef.current += 1
      loadRequestSequenceRef.current += 1
      operationLockRef.current = false
    }
  }, [])

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
  const builderMutationDisabled = mutationDisabled || builderInteractionDisabled
  const handleCapabilityMutationBlocked = useCallback((blocked: boolean) => {
    setCapabilityMutationBlocked(blocked)
  }, [])
  const handleNodeValidityChange = useCallback((nodeId: string, valid: boolean) => {
    if (isBuilderMutationBlocked()) return
    setInvalidDraftNodeIds((current) => {
      const next = new Set(current)
      if (valid) next.delete(nodeId)
      else next.add(nodeId)
      return next
    })
  }, [isBuilderMutationBlocked])

  // Custom node change handler for history.
  const handleNodesChange = useCallback(
    (changes: NodeChange[]) => {
      if (isBuilderMutationBlocked()) return
      if (!isHistoryActionRef.current) {
        // Record history only for non-undo/redo actions.
        addToHistory()
      }
      onNodesChange(changes)
    },
    [isBuilderMutationBlocked, nodes, edges, onNodesChange]
  )

  // Custom edge change handler for history.
  const handleEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      if (isBuilderMutationBlocked()) return
      if (!isHistoryActionRef.current) {
        // Record history only for non-undo/redo actions.
        addToHistory()
      }
      onEdgesChange(changes)
    },
    [isBuilderMutationBlocked, nodes, edges, onEdgesChange]
  )

  // Handle direct node set (layout switching).
  const handleNodesSet = useCallback(
    (newNodes: Node[]) => {
      if (isBuilderMutationBlocked()) return
      // Record history.
      if (!isHistoryActionRef.current) {
        addToHistory()
      }
      setNodes(newNodes)
    },
    [isBuilderMutationBlocked, setNodes]
  )

  // Handle direct edge set (layout switching).
  const handleEdgesSet = useCallback(
    (newEdges: Edge[]) => {
      if (isBuilderMutationBlocked()) return
      setEdges(newEdges)
    },
    [isBuilderMutationBlocked, setEdges]
  )

  // Handle connection.
  const onConnect = useCallback(
    (connection: Connection) => {
      if (isBuilderMutationBlocked()) return
      if (!isHistoryActionRef.current) {
        // Record history.
        addToHistory()
      }
      setEdges((eds) => addEdge(connection, eds))
    },
    [isBuilderMutationBlocked, setEdges]
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

      if (isBuilderMutationBlocked()) return

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
    [capabilityMutationBlocked, isBuilderMutationBlocked, reactFlowInstance, setNodes]
  )

  // Handle node click.
  const onNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    if (isBuilderMutationBlocked()) return
    setSelectedNodeId(node.id)
  }, [isBuilderMutationBlocked])

  // Handle node drag start.
  const onDragStart = (event: React.DragEvent<HTMLElement>, nodeType: string, nodeLabel: string) => {
    if (isBuilderMutationBlocked()) {
      event.preventDefault()
      return
    }
    event.dataTransfer.setData('application/reactflow/type', nodeType)
    event.dataTransfer.setData('application/reactflow/label', nodeLabel)
    event.dataTransfer.effectAllowed = 'move'
  }

  // Add new node.
  const addNewNode = (type: CanonicalBuilderType, label: string) => {
    if (isBuilderMutationBlocked() || capabilityMutationBlocked) return
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
    if (isBuilderMutationBlocked()) return
    // Record history.
    addToHistory()
    setNodes((nds) =>
      nds.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, ...newData } } : n))
    )
  }

  // Delete selected node.
  const deleteSelectedNode = () => {
    if (isBuilderMutationBlocked()) return
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

  // Append history entry.
  const addToHistory = () => {
    if (isBuilderMutationBlocked() || isHistoryActionRef.current) return

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
    if (isBuilderMutationBlocked()) return
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
  }, [isBuilderMutationBlocked])

  // Redo action.
  const handleRedo = useCallback(() => {
    if (isBuilderMutationBlocked()) return
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
  }, [isBuilderMutationBlocked])

  const clearWorkflowDraft = useCallback(() => {
    setWorkflowName('')
    setWorkflowDescription('')
    setWorkflowBase(newWorkflowBase())
    setInvalidDraftNodeIds(new Set())
    setSelectedNodeId(null)
    setNodes([])
    setEdges([])
    seedHistory([], [])
  }, [seedHistory, setEdges, setNodes])

  const loadWorkflow = useCallback(async (targetWorkflowId: string | undefined = id): Promise<boolean> => {
    if (!mountedRef.current) return false
    const requestSequence = ++loadRequestSequenceRef.current
    setWorkflowHydration(null)
    pageLoadingRef.current = Boolean(targetWorkflowId)
    setPageLoading(Boolean(targetWorkflowId))
    clearWorkflowDraft()
    if (!targetWorkflowId) return false

    let loaded = false
    try {
      const [workflow, currentVersion] = await Promise.all([
        getWorkflow(targetWorkflowId, { suppressErrorToast: true }),
        getCurrentWorkflowVersionOrNull(targetWorkflowId),
      ])
      if (
        !mountedRef.current
        || requestSequence !== loadRequestSequenceRef.current
        || currentWorkflowIdRef.current !== targetWorkflowId
      ) return false

      let nextNodes = initialNodes
      let nextEdges = initialEdges
      let nextBase = newWorkflowBase()
      let nextName = workflow.name || t('workflow.detail.build.defaultName')
      let nextDescription = workflow.description || ''

      if (currentVersion) {
        const restoredGraph = parseWorkflowVersion(currentVersion)
        nextBase = restoredGraph.base
        if (restoredGraph.name) nextName = restoredGraph.name
        if (restoredGraph.description) nextDescription = restoredGraph.description
        if (restoredGraph.nodes.length) {
          nextNodes = restoredGraph.nodes
          nextEdges = restoredGraph.edges
        }
      }

      setWorkflowName(nextName)
      setWorkflowDescription(nextDescription)
      setWorkflowBase(nextBase)
      setInvalidDraftNodeIds(new Set())
      setSelectedNodeId(null)
      setNodes(nextNodes)
      setEdges(nextEdges)
      seedHistory(nextNodes, nextEdges)
      loaded = true
      return true
    } catch (error) {
      if (
        !mountedRef.current
        || requestSequence !== loadRequestSequenceRef.current
        || currentWorkflowIdRef.current !== targetWorkflowId
      ) return false
      toast.error('Failed to load workflow builder state.')
      console.error('Failed to load workflow builder state:', error)
      return false
    } finally {
      if (
        mountedRef.current
        && requestSequence === loadRequestSequenceRef.current
        && currentWorkflowIdRef.current === targetWorkflowId
      ) {
        pageLoadingRef.current = false
        setPageLoading(false)
        if (loaded) setWorkflowHydration(targetWorkflowId)
      }
    }
  }, [clearWorkflowDraft, id, initialEdges, initialNodes, seedHistory, setEdges, setNodes, setWorkflowHydration, t])

  const persistWorkflowDraft = useCallback(async (operation: BuilderOperation) => {
    const targetWorkflowId = operation.workflowId
    if (
      mutationDisabled
      || !isBuilderOperationActive(operation)
      || !isCurrentWorkflowHydrated(targetWorkflowId)
    ) return
    if (!workflowName.trim()) {
      toast.error(t('workflow.detail.build.toast.nameRequired'))
      return
    }

    try {
      const spec = serializeWorkflowSpec(
        workflowBase,
        workflowName.trim(),
        workflowDescription.trim(),
        nodes,
        edges
      )

      const version = await createWorkflowVersion(targetWorkflowId, {
        graph_json: spec,
      }, { suppressErrorToast: true })
      if (
        !isBuilderOperationActive(operation)
        || !isCurrentWorkflowHydrated(targetWorkflowId)
      ) return
      try {
        await updateWorkflow(targetWorkflowId, {
          name: workflowName.trim(),
          description: workflowDescription.trim() || undefined,
        }, { suppressErrorToast: true })
      } catch (metadataError) {
        if (!isBuilderOperationActive(operation)) return
        toast.error(t('workflow.detail.build.toast.metadataSaveFailed'))
        console.error('Workflow version saved but metadata update failed:', metadataError)
        await loadWorkflow(targetWorkflowId)
        return
      }
      if (!isBuilderOperationActive(operation)) return
      const refreshed = await loadWorkflow(targetWorkflowId)
      if (
        !refreshed
        || !isBuilderOperationActive(operation)
        || !isCurrentWorkflowHydrated(targetWorkflowId)
      ) return
      toast.success(t('workflow.detail.build.toast.saved'))
      return version
    } catch (error) {
      if (!isBuilderOperationActive(operation)) return
      const message = error instanceof CanonicalNodeValidationError
        || error instanceof UnsupportedBuilderNodeError
        || error instanceof UnsupportedWorkflowEdgeError
        ? error.message
        : t('workflow.detail.build.toast.saveFailed')
      toast.error(message)
      console.error('Failed to save workflow version:', error)
    }
  }, [isBuilderOperationActive, isCurrentWorkflowHydrated, loadWorkflow, mutationDisabled, nodes, edges, t, workflowBase, workflowDescription, workflowName])

  // Save workflow.
  const handleSaveWorkflow = useCallback(async () => {
    if (mutationDisabled || isBuilderMutationBlocked()) return
    const operation = beginBuilderOperation(id)
    if (!operation) return
    operationLockRef.current = true
    setSavingWorkflow(true)
    try {
      return await persistWorkflowDraft(operation)
    } finally {
      if (isBuilderOperationActive(operation)) {
        setSavingWorkflow(false)
        operationLockRef.current = false
      }
    }
  }, [beginBuilderOperation, id, isBuilderMutationBlocked, isBuilderOperationActive, mutationDisabled, persistWorkflowDraft])

  const runWorkflow = useCallback(async () => {
    const targetWorkflowId = id
    if (!targetWorkflowId || mutationDisabled || isBuilderMutationBlocked()) return
    const operation = beginBuilderOperation(targetWorkflowId)
    if (!operation) return
    operationLockRef.current = true
    try {
      setExecutingWorkflow(true)
      toast.info(t('workflow.detail.build.toast.preparingRun'))
      const version = await persistWorkflowDraft(operation)
      if (
        !version
        || !isBuilderOperationActive(operation)
        || !isCurrentWorkflowHydrated(targetWorkflowId)
      ) return
      const result = await previewWorkflowVersion(
        targetWorkflowId,
        version.id,
        {},
        { suppressErrorToast: true },
      )
      if (!isBuilderOperationActive(operation)) return
      if (!result.run_id) {
        throw new Error('Workflow execution did not return a run ID')
      }
      navigationRef.current.toRun(result.run_id)
    } catch (error) {
      if (!isBuilderOperationActive(operation)) return
      toast.error(t('workflow.detail.build.toast.runFailed'))
      console.error('Failed to preview workflow version:', error)
    } finally {
      if (isBuilderOperationActive(operation)) {
        setExecutingWorkflow(false)
        operationLockRef.current = false
      }
    }
  }, [beginBuilderOperation, id, isBuilderMutationBlocked, isBuilderOperationActive, isCurrentWorkflowHydrated, mutationDisabled, persistWorkflowDraft, t])

  // Export workflow.
  const handleExportWorkflow = useCallback(() => {
    if (!isCurrentWorkflowHydrated(id)) return
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
  }, [edges, hasInvalidDrafts, id, isCurrentWorkflowHydrated, nodes, t, workflowBase, workflowDescription, workflowName])

  // Import workflow.
  const handleImportWorkflow = useCallback(() => {
    if (isBuilderMutationBlocked()) return
    const importContext = id && isCurrentWorkflowHydrated(id)
      ? { generation: operationGenerationRef.current, workflowId: id }
      : null
    if (!importContext) return
    // Create file input.
    const fileInput = document.createElement('input')
    fileInput.type = 'file'
    fileInput.accept = '.json'

    fileInput.onchange = (e: Event) => {
      if (!isBuilderImportContextActive(importContext)) return
      const target = e.target as HTMLInputElement
      if (!target.files || target.files.length === 0) return

      const file = target.files[0]
      const reader = new FileReader()

      reader.onload = (event) => {
        if (!isBuilderImportContextActive(importContext)) return
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
          if (!isBuilderImportContextActive(importContext)) return
          setImportDialogContext(importContext)
          dialog.confirm({
            title: t('workflow.detail.build.import.title'),
            description: t('workflow.detail.build.import.confirmDescription', { name: importedName }),
            confirmText: t('workflow.detail.build.import.confirm'),
            cancelText: t('workflow.detail.build.import.cancel'),
            onConfirm: () => {
              const isCurrentImport = isBuilderImportContextActive(importContext)
              if (mountedRef.current) setImportDialogContext(null)
              if (!isCurrentImport) return
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
            onCancel: () => {
              if (mountedRef.current) setImportDialogContext(null)
            },
          })
        } catch (error) {
          if (!isBuilderImportContextActive(importContext)) return
          console.error('Failed to import workflow:', error)
          toast.error(t('workflow.detail.build.import.invalidFile'))
        }
      }

      reader.readAsText(file)
    }

    fileInput.click()
  }, [dialog, id, isBuilderImportContextActive, isBuilderMutationBlocked, isCurrentWorkflowHydrated, setEdges, setNodes, t])

  const handleCreateTicketTemplate = useCallback(async () => {
    if (isBuilderMutationBlocked()) return
    const operation = beginBuilderOperation(id)
    if (!operation) return
    operationLockRef.current = true
    try {
      setCreatingTemplate(true)
      const workflow = await createTicketTriageWorkflow(
        { name: 'Ticket triage' },
        { suppressErrorToast: true },
      )
      if (!isBuilderOperationActive(operation)) return
      toast.success(t('workflow.nodeLibrary.templates.ticketTriage.created'))
      navigationRef.current.toWorkflowBuild(workflow.id)
    } catch (error) {
      if (!isBuilderOperationActive(operation)) return
      toast.error(t('workflow.nodeLibrary.templates.ticketTriage.createError'))
      console.error('Failed to create ticket triage workflow:', error)
    } finally {
      if (isBuilderOperationActive(operation)) {
        setCreatingTemplate(false)
        operationLockRef.current = false
      }
    }
  }, [beginBuilderOperation, id, isBuilderMutationBlocked, isBuilderOperationActive, t])

  useEffect(() => {
    operationGenerationRef.current += 1
    operationLockRef.current = false
    setImportDialogContext(null)
    setSavingWorkflow(false)
    setExecutingWorkflow(false)
    setCreatingTemplate(false)
    void loadWorkflow(id)
    return () => {
      operationGenerationRef.current += 1
      loadRequestSequenceRef.current += 1
      operationLockRef.current = false
    }
  }, [id, loadWorkflow])

  // The import confirmation only belongs to the render that owns it: same
  // workflow, same operation generation, still hydrated.
  const importDialogOpen = Boolean(
    importDialogContext
    && importDialogContext.workflowId === id
    && importDialogContext.generation === operationGenerationRef.current
    && builderHydrated
  )

  return {
    // Graph state.
    nodes,
    edges,
    selectedNode,
    // Workflow metadata.
    workflowName,
    workflowDescription,
    setWorkflowName,
    setWorkflowDescription,
    // Canvas wiring.
    reactFlowWrapper,
    setReactFlowInstance,
    handleNodesChange,
    handleEdgesChange,
    handleNodesSet,
    handleEdgesSet,
    onConnect,
    onDrop,
    onDragOver,
    onNodeClick,
    onDragStart,
    addNewNode,
    updateNodeData,
    deleteSelectedNode,
    // History.
    undoable,
    redoable,
    handleUndo,
    handleRedo,
    // Operations.
    handleSaveWorkflow,
    handleExportWorkflow,
    handleImportWorkflow,
    handleCreateTicketTemplate,
    runWorkflow,
    creatingTemplate,
    // Gating.
    builderHydrated,
    builderInteractionDisabled,
    builderMutationDisabled,
    hasCompatibilityNodes,
    hasUnsupportedEdges,
    hasInvalidDrafts,
    handleCapabilityMutationBlocked,
    handleNodeValidityChange,
    // Import confirmation dialog.
    importDialogOpen,
    DialogComponent,
  }
}

export type WorkflowBuilder = ReturnType<typeof useWorkflowBuilder>
