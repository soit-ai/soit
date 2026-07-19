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
  type WorkflowVersion,
} from '@/services/workflow-service'

// Import node types and metadata.
import { getDefaultNodeData } from './ui/build/nodes'

// Import custom components.
import WorkflowInfoPanel from './ui/build/workflow-info-panel'
import NodeLibraryPanel from './ui/build/node-library-panel'
import NodePropertiesPanel from './ui/build/node-properties-panel'
import WorkflowEditor from './ui/build/workflow-editor'
import { Card, CardContent } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'

interface BuildPageProps { }

const runtimeNodeTypeMap: Record<string, string> = {
  'text-node': 'transform',
  'prompt-node': 'transform',
  'llm-node': 'llm',
  'tool-node': 'tool',
  'data-node': 'transform',
  'output-node': 'output',
  'knowledge-search-node': 'retrieve',
  'agent-node': 'node',
  'question-classifier-node': 'llm',
  'logic-node': 'condition',
  'conditional-node': 'condition',
  'delivery-node': 'transform',
  'loop-node': 'condition',
  'transform-node': 'transform',
  'code-execution-node': 'transform',
  'template-transform-node': 'transform',
  'variable-aggregator-node': 'transform',
  'document-extractor-node': 'transform',
  'variable-assignment-node': 'set_var',
  'parameter-extractor-node': 'transform',
  'end-node': 'output',
}

const builderNodeTypeMap: Record<string, string> = {
  transform: 'transform-node',
  llm: 'llm-node',
  tool: 'tool-node',
  retrieve: 'knowledge-search-node',
  condition: 'conditional-node',
  output: 'output-node',
  set_var: 'variable-assignment-node',
  node: 'agent-node',
}

const normalizeBuilderType = (builderType?: string | null, runtimeType?: string | null) => {
  if (builderType && getDefaultNodeData(builderType)) {
    return builderType
  }
  if (runtimeType && builderNodeTypeMap[runtimeType]) {
    return builderNodeTypeMap[runtimeType]
  }
  return 'transform-node'
}

const toModelRef = (value?: string) => {
  const trimmed = value?.trim()
  if (!trimmed) {
    return 'model:openai:gpt-5.1'
  }
  return trimmed
}

const toStepOutputRef = (nodeId: string, field?: string) => {
  return field ? `{{ steps.${nodeId}.output.${field} }}` : `{{ steps.${nodeId}.output }}`
}

const buildRuntimeNodeParams = (node: Node, incomingNodeIds: string[]) => {
  const data = (node.data || {}) as Record<string, any>
  const primaryInput = incomingNodeIds[0]
  const primaryTextRef = primaryInput ? toStepOutputRef(primaryInput, 'text') : undefined
  const primaryOutputRef = primaryInput ? toStepOutputRef(primaryInput) : undefined

  switch (node.type) {
    case 'text-node':
      return {
        mapping: {
          text: data.content || '',
        },
      }
    case 'prompt-node':
      return {
        mapping: {
          prompt: data.template || '',
        },
      }
    case 'llm-node':
      return {
        prompt: data.prompt || primaryTextRef || primaryOutputRef || '',
        system: data.systemPrompt || undefined,
        model: toModelRef(data.modelName),
        temperature: data.temperature,
        max_tokens: data.maxTokens,
      }
    case 'knowledge-search-node':
      return {
        query: data.query || primaryTextRef || primaryOutputRef || '',
        collection: data.customSource || data.source || data.dataSource || 'knowledge_base',
        top_k: data.topK || 3,
        embedding_model: toModelRef(data.embeddingModel || data.modelName || 'model:openai:text-embedding-3-small'),
      }
    case 'tool-node':
      return {
        tool_ref: data.toolName || '',
        arguments: data.parameters || {},
        input: primaryOutputRef || undefined,
      }
    case 'conditional-node':
    case 'logic-node':
      return {
        condition: data.condition || data.expression || 'true',
        value: primaryOutputRef || undefined,
      }
    case 'output-node':
    case 'end-node':
      return {
        value: primaryOutputRef || undefined,
      }
    case 'variable-assignment-node':
      return {
        key: data.variableName || data.key || 'value',
        value: data.value || primaryOutputRef || '',
      }
    case 'agent-node':
      return {
        node_ref: data.agentId || data.nodeRef || '',
        input: primaryOutputRef || undefined,
      }
    default:
      return {
        mapping: {
          value: primaryOutputRef || data.content || data.template || data.source || data.script || '',
        },
      }
  }
}

const builderGraphToWorkflowSpec = (workflowName: string, workflowDescription: string, nodes: Node[], edges: Edge[]) => {
  const incomingMap = new Map<string, string[]>()
  edges.forEach((edge) => {
    const current = incomingMap.get(edge.target) || []
    current.push(edge.source)
    incomingMap.set(edge.target, current)
  })

  return {
    name: workflowName,
    description: workflowDescription,
    inputs_schema: { type: 'object', properties: {} },
    outputs_schema: { type: 'object', properties: { value: { type: 'object' } } },
    graph: {
      nodes: nodes.map((node) => ({
        id: node.id,
        type: runtimeNodeTypeMap[node.type || ''] || 'transform',
        name: typeof node.data?.label === 'string' ? node.data.label : node.id,
        params: buildRuntimeNodeParams(node, incomingMap.get(node.id) || []),
        ui: {
          position: node.position,
          builder_type: node.type,
          data: node.data,
        },
      })),
      edges: edges.map((edge) => ({
        id: edge.id,
        from: edge.source,
        to: edge.target,
        from_port: edge.sourceHandle || null,
        to_port: edge.targetHandle || null,
        condition:
          edge.sourceHandle === 'output-true'
            ? 'true'
            : edge.sourceHandle === 'output-false'
              ? 'false'
              : null,
      })),
    },
  }
}

const workflowSpecToBuilderGraph = (version: WorkflowVersion | null) => {
  const graph = version?.graph_json?.graph as Record<string, any> | undefined
  const rawNodes = Array.isArray(graph?.nodes) ? graph?.nodes : []
  const rawEdges = Array.isArray(graph?.edges) ? graph?.edges : []

  if (!rawNodes.length) {
    return null
  }

  const nodes: Node[] = rawNodes.map((node: Record<string, any>, index: number) => {
    const ui = (node.ui || {}) as Record<string, any>
    const builderType = normalizeBuilderType(typeof ui.builder_type === 'string' ? ui.builder_type : null, node.type)
    const uiData = (ui.data || {}) as Record<string, any>
    const defaultData = getDefaultNodeData(builderType)
    const params = (node.params || {}) as Record<string, any>
    const position = ui.position && typeof ui.position.x === 'number' && typeof ui.position.y === 'number'
      ? ui.position
      : { x: 120 + index * 240, y: 140 }

    return {
      id: node.id,
      type: builderType,
      position,
      data: {
        ...defaultData,
        ...uiData,
        label: uiData.label || node.name || defaultData.label || node.id,
        content: uiData.content ?? params.mapping?.text ?? uiData.content,
        template: uiData.template ?? params.mapping?.prompt ?? uiData.template,
        modelName: uiData.modelName ?? params.model ?? uiData.modelName,
        temperature: uiData.temperature ?? params.temperature ?? uiData.temperature,
        maxTokens: uiData.maxTokens ?? params.max_tokens ?? uiData.maxTokens,
        systemPrompt: uiData.systemPrompt ?? params.system ?? uiData.systemPrompt,
        query: uiData.query ?? params.query ?? uiData.query,
        customSource: uiData.customSource ?? params.collection ?? uiData.customSource,
        topK: uiData.topK ?? params.top_k ?? uiData.topK,
        toolName: uiData.toolName ?? params.tool_ref ?? uiData.toolName,
        parameters: uiData.parameters ?? params.arguments ?? uiData.parameters,
        condition: uiData.condition ?? params.condition ?? uiData.condition,
      },
    }
  })

  const edges: Edge[] = rawEdges.map((edge: Record<string, any>) => ({
    id: edge.id,
    source: edge.from,
    target: edge.to,
    sourceHandle:
      typeof edge.from_port === 'string'
        ? edge.from_port
        : edge.condition === 'true'
          ? 'output-true'
          : edge.condition === 'false'
            ? 'output-false'
            : undefined,
    targetHandle: typeof edge.to_port === 'string' ? edge.to_port : undefined,
  }))

  return {
    name: typeof version?.graph_json?.name === 'string' ? version.graph_json.name : '',
    description: typeof version?.graph_json?.description === 'string' ? version.graph_json.description : '',
    nodes,
    edges,
  }
}

const BuildPage: React.FC<BuildPageProps> = () => {
  const { t } = useTranslation()
  const { id } = useParams()
  const navigate = useNavigate()
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const [reactFlowInstance, setReactFlowInstance] = useState<any>(null)
  const [pageLoading, setPageLoading] = useState(false)
  const [savingWorkflow, setSavingWorkflow] = useState(false)
  const [creatingTemplate, setCreatingTemplate] = useState(false)

  // State management.
  const [workflowName, setWorkflowName] = useState(() => t('workflow.detail.build.defaultName'))
  const [workflowDescription, setWorkflowDescription] = useState('')
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)

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

  // Initial nodes and edges.
  const initialNodes = useMemo<Node[]>(() => [
    {
      id: 'input-1',
      type: 'text-node',
      position: { x: 100, y: 100 },
      data: { ...getDefaultNodeData('text-node'), label: t('workflow.detail.nodes.text.label') },
    },
    {
      id: 'llm-1',
      type: 'llm-node',
      position: { x: 400, y: 100 },
      data: { ...getDefaultNodeData('llm-node'), label: t('workflow.detail.nodes.llm.label') },
    },
    {
      id: 'output-1',
      type: 'output-node',
      position: { x: 700, y: 100 },
      data: { ...getDefaultNodeData('output-node'), label: t('workflow.detail.nodes.output.label') },
    },
  ], [t])

  const initialEdges = useMemo<Edge[]>(() => [
    { id: 'e1-2', source: 'input-1', target: 'llm-1' },
    { id: 'e2-3', source: 'llm-1', target: 'output-1' },
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
      if (!reactFlowBounds || !reactFlowInstance) return

      const type = event.dataTransfer.getData('application/reactflow/type')
      const label = event.dataTransfer.getData('application/reactflow/label')

      // Validate node type.
      if (!type) return

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
    [reactFlowInstance, setNodes]
  )

  // Handle node click.
  const onNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    setSelectedNode(node)
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
  const onDragStart = (event: React.DragEvent<HTMLDivElement>, nodeType: string, nodeLabel: string) => {
    event.dataTransfer.setData('application/reactflow/type', nodeType)
    event.dataTransfer.setData('application/reactflow/label', nodeLabel)
    event.dataTransfer.effectAllowed = 'move'
  }

  // Add new node.
  const addNewNode = (type: string, label: string) => {
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
    if (selectedNode) {
      // Record history.
      addToHistory()
      setNodes((nds) => nds.filter((node) => node.id !== selectedNode.id))
      setEdges((eds) => eds.filter(
        (edge) => edge.source !== selectedNode.id && edge.target !== selectedNode.id
      ))
      setSelectedNode(null)
    }
  }

  // Run workflow.
  const runWorkflow = () => {
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

      const restoredGraph = workflowSpecToBuilderGraph(currentVersion)
      if (restoredGraph) {
        setNodes(restoredGraph.nodes)
        setEdges(restoredGraph.edges)
        if (restoredGraph.name) {
          setWorkflowName(restoredGraph.name)
        }
        if (restoredGraph.description) {
          setWorkflowDescription(restoredGraph.description)
        }
        seedHistory(restoredGraph.nodes, restoredGraph.edges)
        return
      }

      seedHistory(initialNodes, initialEdges)
    } catch (error) {
      toast.error('Failed to load workflow builder state.')
      console.error('Failed to load workflow builder state:', error)
      seedHistory(initialNodes, initialEdges)
    } finally {
      setPageLoading(false)
    }
  }, [id, initialEdges, initialNodes, seedHistory, setEdges, setNodes, t])

  // Save workflow.
  const handleSaveWorkflow = useCallback(async () => {
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
      const spec = builderGraphToWorkflowSpec(workflowName.trim(), workflowDescription.trim(), nodes, edges)
      const createdBy =
        (typeof window !== 'undefined' && (localStorage.getItem('user_id') || localStorage.getItem('username'))) ||
        'system'

      await updateWorkflow(id, {
        name: workflowName.trim(),
        description: workflowDescription.trim() || undefined,
      })
      await createWorkflowVersion(id, {
        graph_json: spec,
        created_by: createdBy,
      })
      toast.success(t('workflow.detail.build.toast.saved'))
      await loadWorkflow()
    } catch (error) {
      toast.error('Failed to save workflow version.')
      console.error('Failed to save workflow version:', error)
    } finally {
      setSavingWorkflow(false)
    }
  }, [id, loadWorkflow, nodes, edges, t, workflowDescription, workflowName])

  // Export workflow.
  const handleExportWorkflow = useCallback(() => {
    if (!workflowName.trim()) {
      toast.error(t('workflow.detail.build.toast.nameRequired'))
      return
    }

    const workflowData = {
      name: workflowName,
      description: workflowDescription,
      nodes,
      edges,
      exportTime: new Date().toISOString(),
      version: '1.0.0',
    }

    // Create download link.
    const dataStr = JSON.stringify(workflowData, null, 2)
    const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr)

    const exportFileName = `${workflowName.replace(/\s+/g, '_')}_${new Date().getTime()}.json`

    const linkElement = document.createElement('a')
    linkElement.setAttribute('href', dataUri)
    linkElement.setAttribute('download', exportFileName)
    linkElement.click()

    toast.success(t('workflow.detail.build.toast.exported'))
  }, [workflowName, workflowDescription, nodes, edges, t])

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

          const workflowData = JSON.parse(result)

          // Validate imported data.
          if (!workflowData.nodes || !workflowData.edges) {
            throw new Error(t('workflow.detail.build.import.invalidData'))
          }

          const importedName = workflowData.name || t('workflow.detail.build.import.unnamed')

          // Confirm import.
          dialog.confirm({
            title: t('workflow.detail.build.import.title'),
            description: t('workflow.detail.build.import.confirmDescription', { name: importedName }),
            onConfirm: () => {
              // Record history.
              addToHistory()

              // Update workflow data.
              setWorkflowName(workflowData.name || t('workflow.detail.build.import.importedFallbackName'))
              setWorkflowDescription(workflowData.description || '')
              setNodes(workflowData.nodes)
              setEdges(workflowData.edges)

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
  }, [dialog, t])

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
          className="border-1 rounded-lg px-2"
        />
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col h-full w-full">
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
    </div>
  )
}

export default BuildPage
