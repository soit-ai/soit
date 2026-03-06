import React, { useState, useCallback, useRef, useEffect } from 'react'
import { useTranslation } from '@/i18n'
import { useParams } from 'react-router'
import { useNavigate } from '@/hooks/use-navigate'
import { useNodesState, useEdgesState, addEdge, ReactFlowProvider } from '@xyflow/react'
import type { Node, Edge, Connection, NodeChange, EdgeChange } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Separator } from '@/components/ui/separator'
import { toast } from 'sonner'
import useDialog from '@/hooks/use-dialog'

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

const BuildPage: React.FC<BuildPageProps> = () => {
  const { t } = useTranslation()
  const { id } = useParams()
  const navigate = useNavigate()
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const [reactFlowInstance, setReactFlowInstance] = useState<any>(null)

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
  const initialNodes: Node[] = [
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
  ]

  const initialEdges: Edge[] = [
    { id: 'e1-2', source: 'input-1', target: 'llm-1' },
    { id: 'e2-3', source: 'llm-1', target: 'output-1' },
  ]

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

    console.log('Saving workflow:', workflow)
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

  // Save workflow.
  const handleSaveWorkflow = useCallback(() => {
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

    console.log('Saving workflow:', workflow)
    toast.success(t('workflow.detail.build.toast.saved'))
  }, [id, workflowName, workflowDescription, nodes, edges, t])

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

  // Initialize history.
  useEffect(() => {
    // Seed initial state into history.
    setHistory({
      nodes: [initialNodes],
      edges: [initialEdges],
      currentIndex: 0,
    })
    setUndoable(false)
    setRedoable(false)
  }, [])

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
            />
          </ReactFlowProvider>
        </div>
      </div>
    </div>
  )
}

export default BuildPage
