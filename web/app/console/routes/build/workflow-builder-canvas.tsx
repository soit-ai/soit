import { useMemo } from 'react'

import { ReactFlowProvider } from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { useTranslation } from '@/i18n'
import {
  useWorkflowBuilder,
  type WorkflowBuilderNavigation,
} from '@/features/workflow-builder/use-workflow-builder'

// The interactive builder is reused from the legacy tree, not reimplemented:
// one canvas, one node library, one properties panel, one set of behaviours.
import NodeLibraryPanel from '@/routes/workflow/detail/ui/build/node-library-panel'
import NodePropertiesPanel from '@/routes/workflow/detail/ui/build/node-properties-panel'
import WorkflowEditor from '@/routes/workflow/detail/ui/build/workflow-editor'
import WorkflowInfoPanel from '@/routes/workflow/detail/ui/build/workflow-info-panel'

import { useConsoleNavigate } from '../../shell/use-console-navigate'

interface WorkflowBuilderCanvasProps {
  /** Undefined while the route is a draft placeholder (`new`, `new-draft`). */
  workflowId?: string
}

/**
 * The console (v2) Build tab canvas: the legacy ReactFlow editor and its panels
 * hosted inside the prototype's `.wfshell` frame (palette | canvas | inspector).
 * Every behaviour comes from `useWorkflowBuilder`, which the legacy
 * `/workflow/:id/build` page renders too — only the navigation targets and the
 * surrounding chrome differ.
 *
 * Loaded lazily by `workflow-detail.tsx` so `@xyflow/react` and the node
 * registry stay out of the console's initial JavaScript.
 */
export default function WorkflowBuilderCanvas({ workflowId }: WorkflowBuilderCanvasProps) {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()

  const navigation = useMemo<WorkflowBuilderNavigation>(() => ({
    toRun: (runId) => navigate(`/v2/observe/runs/${runId}`),
    toWorkflowBuild: (id) => navigate(`/v2/build/workflows/${id}`),
  }), [navigate])

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
    hasInvalidDrafts,
    handleCapabilityMutationBlocked,
    handleNodeValidityChange,
    importDialogOpen,
    DialogComponent,
  } = useWorkflowBuilder({ workflowId, navigation })

  return (
    <>
      <div className="wfshell wfshell-live">
        <div className="panel palette">
          <div className="pcap">{t('console.wfDetail.nodesCap')}</div>
          <fieldset disabled={builderInteractionDisabled} className="wfpalette-body">
            <WorkflowInfoPanel
              workflowName={builderHydrated ? workflowName : ''}
              workflowDescription={builderHydrated ? workflowDescription : ''}
              setWorkflowName={setWorkflowName}
              setWorkflowDescription={setWorkflowDescription}
            />
            <NodeLibraryPanel
              onDragStart={onDragStart}
              addNewNode={addNewNode}
              onCreateTicketTemplate={handleCreateTicketTemplate}
              creatingTicketTemplate={creatingTemplate}
              onMutationBlockedChange={handleCapabilityMutationBlocked}
            />
          </fieldset>
          <div className="phint">{t('console.wfDetail.paletteHint')}</div>
        </div>

        <div className="canvas-wrap wfcanvas">
          <ReactFlowProvider>
            <WorkflowEditor
              ref={reactFlowWrapper}
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
              workflowId={workflowId || ''}
              workflowName={builderHydrated ? workflowName : ''}
            />
          </ReactFlowProvider>
        </div>

        <div className="panel inspector">
          <fieldset disabled={builderInteractionDisabled} className="wfinspector-body">
            <NodePropertiesPanel
              selectedNode={builderHydrated ? selectedNode : null}
              updateNodeData={updateNodeData}
              onNodeValidityChange={handleNodeValidityChange}
            />
          </fieldset>
        </div>
      </div>
      {importDialogOpen ? <DialogComponent /> : null}
    </>
  )
}
