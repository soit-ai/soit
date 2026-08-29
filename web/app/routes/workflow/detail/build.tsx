import React, { useMemo } from 'react'
import { useTranslation } from '@/i18n'
import { useParams } from 'react-router'
import { useNavigate } from '@/hooks/use-navigate'
import { ReactFlowProvider } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Separator } from '@/components/ui/separator'
import { Card, CardContent } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'

// The builder orchestration is shared with the console (v2) Build tab.
import {
  useWorkflowBuilder,
  type WorkflowBuilderNavigation,
} from '@/features/workflow-builder/use-workflow-builder'

// Import custom components.
import WorkflowInfoPanel from './ui/build/workflow-info-panel'
import NodeLibraryPanel from './ui/build/node-library-panel'
import NodePropertiesPanel from './ui/build/node-properties-panel'
import WorkflowEditor from './ui/build/workflow-editor'

interface BuildPageProps { }

const BuildPage: React.FC<BuildPageProps> = () => {
  const { t } = useTranslation()
  const { id } = useParams()
  const navigate = useNavigate()

  const navigation = useMemo<WorkflowBuilderNavigation>(() => ({
    toRun: (runId) => navigate(`/observe/runs/${runId}`),
    toWorkflowBuild: (workflowId) => navigate(`/workflow/${workflowId}/build`),
  }), [navigate])

  const builder = useWorkflowBuilder({ workflowId: id, navigation })
  const {
    nodes,
    edges,
    selectedNode,
    workflowName,
    workflowDescription,
    setWorkflowName,
    setWorkflowDescription,
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
    undoable,
    redoable,
    handleUndo,
    handleRedo,
    handleSaveWorkflow,
    handleExportWorkflow,
    handleImportWorkflow,
    handleCreateTicketTemplate,
    runWorkflow,
    creatingTemplate,
    builderHydrated,
    builderInteractionDisabled,
    builderMutationDisabled,
    hasCompatibilityNodes,
    hasUnsupportedEdges,
    hasInvalidDrafts,
    handleCapabilityMutationBlocked,
    handleNodeValidityChange,
    importDialogOpen,
    DialogComponent,
  } = builder

  const renderLeftPanel = () => {
    return (
      <div className="w-80 m-0 mb-2 p-2 bg-background flex flex-col h-full">
        <Card className="w-full h-full shadow-none border-1 rounded-lg">
          <CardContent className="px-2 h-full overflow-hidden">
            <fieldset disabled={builderInteractionDisabled} className="contents">
              <WorkflowInfoPanel
                workflowName={builderHydrated ? workflowName : ''}
                workflowDescription={builderHydrated ? workflowDescription : ''}
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
            </fieldset>
          </CardContent>
        </Card>
      </div>
    )
  }

  const renderRightPanel = () => {
    return (
      <div className="w-100 m-0 mb-2 p-2 bg-background flex flex-col h-full">
        <fieldset disabled={builderInteractionDisabled} className="contents">
          <NodePropertiesPanel
            selectedNode={builderHydrated ? selectedNode : null}
            updateNodeData={updateNodeData}
            onNodeValidityChange={handleNodeValidityChange}
            className="border-1 rounded-lg px-2"
          />
        </fieldset>
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col h-full w-full">
      {(hasCompatibilityNodes || hasUnsupportedEdges) && (
        <div role="alert" className="mx-2 mb-1 rounded-md border border-warning/50 bg-warning/10 px-3 py-2 text-sm">
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
              nodes={builderHydrated ? nodes : []}
              edges={builderHydrated ? edges : []}
              onNodesChange={handleNodesChange}
              onEdgesChange={handleEdgesChange}
              onConnect={onConnect}
              onInit={setReactFlowInstance}
              onDrop={onDrop}
              onDragOver={onDragOver}
              onNodeClick={onNodeClick}
              selectedNode={builderHydrated ? selectedNode : null}
              deleteSelectedNode={deleteSelectedNode}
              runWorkflow={runWorkflow}
              mutationDisabled={builderMutationDisabled}
              interactionDisabled={builderInteractionDisabled}
              exportDisabled={hasInvalidDrafts || !builderHydrated}
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
              workflowName={builderHydrated ? workflowName : ''}
            />
          </ReactFlowProvider>
        </div>
      </div>
      {importDialogOpen ? <DialogComponent /> : null}
    </div>
  )
}

export default BuildPage
