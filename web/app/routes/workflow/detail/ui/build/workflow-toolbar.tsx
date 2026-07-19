import React from 'react'
import { Panel, type ReactFlowInstance } from '@xyflow/react'
import { ZoomIn, ZoomOut, Save, RotateCcw, Download, Upload, Undo, Redo, LayoutGrid, GitBranchPlus } from 'lucide-react'
import { useLayoutStore, type LayoutDirection } from './layout-store'
import { useTranslation } from '@/i18n'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import type { Node, Edge } from '@xyflow/react'

interface WorkflowToolbarProps {
  flowInstance: ReactFlowInstance | null
  onZoomIn: () => void
  onZoomOut: () => void
  onResetView: () => void
  onUndo: () => void
  onRedo: () => void
  onSave: () => void
  onExport: () => void
  onImport: () => void
  getLayoutedElements?: (nodes: Node[], edges: Edge[], direction?: string) => { nodes: Node[]; edges: Edge[]; }
  undoable: boolean
  redoable: boolean
  saveDisabled?: boolean
  exportDisabled?: boolean
}

const WorkflowToolbar: React.FC<WorkflowToolbarProps> = ({
  flowInstance,
  onZoomIn,
  onZoomOut,
  onResetView,
  onUndo,
  onRedo,
  onSave,
  onExport,
  onImport,
  getLayoutedElements,
  undoable,
  redoable,
  saveDisabled = false,
  exportDisabled = false,
}) => {
  const { t } = useTranslation()
  const { direction: layoutDirection, setDirection: setLayoutDirection } = useLayoutStore();
  const getLayoutChange = (direction: LayoutDirection) => {
    setLayoutDirection(direction);
    if (flowInstance && getLayoutedElements) {
      const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
        flowInstance.getNodes(),
        flowInstance.getEdges(),
        direction
      );
      flowInstance.setNodes(layoutedNodes);
      flowInstance.setEdges(layoutedEdges);
      // Fit the view after re-layout.
      setTimeout(() => {
        if (flowInstance) {
          flowInstance.fitView({ padding: 0.2, minZoom: 1, maxZoom: 1 });
        }
      }, 50);
    }
  }
  return (
    <Panel position="bottom-center" className="flex justify-center w-full mb-2 z-10">
      <div className="bg-background/80 backdrop-blur-md border rounded-full shadow-md p-2 flex gap-2">
        <TooltipProvider>
          <Tooltip delayDuration={300}>
            <TooltipTrigger asChild>
              <Button
                size="icon"
                variant="ghost"
                className="h-8 w-8"
                onClick={onUndo}
                disabled={!undoable}
              >
                <Undo className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">
              <p>{t('workflow.common.undo')}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>

        <TooltipProvider>
          <Tooltip delayDuration={300}>
            <TooltipTrigger asChild>
              <Button
                size="icon"
                variant="ghost"
                className="h-8 w-8"
                onClick={onRedo}
                disabled={!redoable}
              >
                <Redo className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">
              <p>{t('workflow.common.redo')}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>

        <div className="h-8 w-px bg-border mx-1"></div>

        <TooltipProvider>
          <Tooltip delayDuration={300}>
            <TooltipTrigger asChild>
              <Button
                size="icon"
                variant="ghost"
                className="h-8 w-8"
                onClick={onZoomIn}
              >
                <ZoomIn className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">
              <p>{t('workflow.operator.zoomIn')}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>

        <TooltipProvider>
          <Tooltip delayDuration={300}>
            <TooltipTrigger asChild>
              <Button
                size="icon"
                variant="ghost"
                className="h-8 w-8"
                onClick={onZoomOut}
              >
                <ZoomOut className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">
              <p>{t('workflow.operator.zoomOut')}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>

        <TooltipProvider>
          <Tooltip delayDuration={300}>
            <TooltipTrigger asChild>
              <Button
                size="icon"
                variant="ghost"
                className="h-8 w-8"
                onClick={onResetView}
              >
                <RotateCcw className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">
              <p>{t('workflow.operator.resetView')}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>

        <div className="h-8 w-px bg-border mx-1"></div>

        <TooltipProvider>
          <Tooltip delayDuration={300}>
            <TooltipTrigger asChild>
              <Button
                size="icon"
                variant="ghost"
                className="h-8 w-8"
                aria-label={t('workflow.operator.saveWorkflow')}
                disabled={saveDisabled}
                onClick={onSave}
              >
                <Save className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">
              <p>{t('workflow.operator.saveWorkflow')}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>

        <TooltipProvider>
          <Tooltip delayDuration={300}>
            <TooltipTrigger asChild>
              <Button
                size="icon"
                variant="ghost"
                className="h-8 w-8"
                aria-label={t('workflow.operator.exportWorkflow')}
                aria-describedby={exportDisabled ? 'workflow-export-disabled-reason' : undefined}
                disabled={exportDisabled}
                onClick={onExport}
              >
                <Download className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">
              <p>{exportDisabled
                ? t('workflow.detail.build.export.invalidDraft')
                : t('workflow.operator.exportWorkflow')}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        {exportDisabled && (
          <span id="workflow-export-disabled-reason" className="sr-only">
            {t('workflow.detail.build.export.invalidDraft')}
          </span>
        )}

        <TooltipProvider>
          <Tooltip delayDuration={300}>
            <TooltipTrigger asChild>
              <Button
                size="icon"
                variant="ghost"
                className="h-8 w-8"
                aria-label={t('workflow.operator.importWorkflow')}
                onClick={onImport}
              >
                <Upload className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">
              <p>{t('workflow.operator.importWorkflow')}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>

        <>
          <div className="h-8 w-px bg-border mx-1"></div>

          <TooltipProvider>
            <Tooltip delayDuration={300}>
              <TooltipTrigger asChild>
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-8 w-8"
                  onClick={() => {
                    const newDirection = layoutDirection === 'TB' ? 'LR' : 'TB';
                    // Update the global layout state.
                    setLayoutDirection(newDirection);
                    // Trigger the layout change handler.
                    if (getLayoutChange) {
                      getLayoutChange(newDirection);
                    }
                  }}
                >
                  {layoutDirection === 'TB' ? (
                    <GitBranchPlus className="h-4 w-4" />
                  ) : (
                    <LayoutGrid className="h-4 w-4" />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent side="top">
                <p>
                  {layoutDirection === 'TB'
                    ? t('workflow.operator.layoutHorizontal')
                    : t('workflow.operator.layoutTree')}
                </p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </>
      </div>
    </Panel>
  )
}

export default WorkflowToolbar
