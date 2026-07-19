import React, { useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BotMessageSquare, Cpu, Database, MessageSquare, TicketCheck, Workflow, Wrench } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useTranslation } from '@/i18n'
import type { TranslationKey } from '@/i18n/types'
import { getWorkflowCapabilities, type WorkflowCapabilitiesResponse } from '@/services/workflow-service'
import {
  canonicalBuilderTypes,
  runtimeTypeByBuilderType,
  type CanonicalBuilderType,
} from './canonical-node-registry'
import { getDefaultNodeData, nodeCategories, nodeTypeInfo, nodeTypes, propertyPanels } from './nodes'

export const workflowCapabilitiesQueryKey = ['workflow', 'capabilities', 'builder'] as const

interface NodeLibraryPanelProps {
  onDragStart: (event: React.DragEvent<HTMLElement>, nodeType: string, nodeLabel: string) => void
  addNewNode: (type: CanonicalBuilderType, label: string) => void
  onCreateTicketTemplate?: () => void
  creatingTicketTemplate?: boolean
  onMutationBlockedChange?: (blocked: boolean) => void
}

type CapabilityContract =
  | { status: 'loading' | 'error' | 'empty' | 'mismatch'; capabilities: [] }
  | { status: 'ready'; capabilities: WorkflowCapabilitiesResponse['capabilities'] }

const expectedCompatibilityTypes = ['http', 'node'] as const
const categoryByBuilderType = Object.fromEntries(
  nodeCategories.flatMap((category) => category.types.map((type) => [type, category.id])),
) as Record<CanonicalBuilderType, string>

const exactStringArray = (value: unknown, expected: readonly string[]) => {
  return Array.isArray(value)
    && value.length === expected.length
    && value.every((item, index) => item === expected[index])
}

const validateWorkflowCapabilities = (response: WorkflowCapabilitiesResponse | undefined): CapabilityContract => {
  if (!response || !Array.isArray(response.capabilities)) return { status: 'mismatch', capabilities: [] }
  if (!response.capabilities.length) return { status: 'empty', capabilities: [] }
  if (response.capabilities.length !== canonicalBuilderTypes.length) return { status: 'mismatch', capabilities: [] }

  const expectedRuntimeTypes = canonicalBuilderTypes.map((builderType) => runtimeTypeByBuilderType[builderType])
  if (!exactStringArray(response.builder_node_types, expectedRuntimeTypes)) return { status: 'mismatch', capabilities: [] }
  if (!exactStringArray(response.compatibility_node_types, expectedCompatibilityTypes)) return { status: 'mismatch', capabilities: [] }

  const runtimeTypes = new Set<string>()
  const uiTypes = new Set<string>()
  for (const [index, capability] of response.capabilities.entries()) {
    const expectedUiType = canonicalBuilderTypes[index]
    const expectedRuntimeType = runtimeTypeByBuilderType[expectedUiType]
    if (
      !capability
      || capability.type !== expectedRuntimeType
      || capability.ui_type !== expectedUiType
      || capability.category !== categoryByBuilderType[expectedUiType]
      || capability.executable !== true
      || !(expectedUiType in nodeTypes)
      || !(expectedUiType in propertyPanels)
      || getDefaultNodeData(expectedUiType) === undefined
      || runtimeTypes.has(capability.type)
      || uiTypes.has(capability.ui_type)
    ) {
      return { status: 'mismatch', capabilities: [] }
    }
    runtimeTypes.add(capability.type)
    uiTypes.add(capability.ui_type)
  }

  return { status: 'ready', capabilities: response.capabilities }
}

const NodeLibraryPanel: React.FC<NodeLibraryPanelProps> = ({
  onDragStart,
  addNewNode,
  onCreateTicketTemplate,
  creatingTicketTemplate = false,
  onMutationBlockedChange,
}) => {
  const { t } = useTranslation()
  const capabilityQuery = useQuery({
    queryKey: workflowCapabilitiesQueryKey,
    queryFn: getWorkflowCapabilities,
    staleTime: 5 * 60 * 1000,
    retry: false,
  })
  const contract = useMemo<CapabilityContract>(() => {
    if (capabilityQuery.isPending) return { status: 'loading', capabilities: [] }
    if (capabilityQuery.isError) return { status: 'error', capabilities: [] }
    return validateWorkflowCapabilities(capabilityQuery.data)
  }, [capabilityQuery.data, capabilityQuery.isError, capabilityQuery.isPending])

  useEffect(() => {
    onMutationBlockedChange?.(contract.status !== 'ready')
  }, [contract.status, onMutationBlockedChange])

  const getIconComponent = (iconName: string) => {
    switch (iconName) {
      case 'MessageSquare': return <MessageSquare className="h-4 w-4" />
      case 'Cpu': return <Cpu className="h-4 w-4" />
      case 'Wrench': return <Wrench className="h-4 w-4" />
      case 'Database': return <Database className="h-4 w-4" />
      case 'BotMessageSquare': return <BotMessageSquare className="h-4 w-4" />
      default: return <Workflow className="h-4 w-4" />
    }
  }

  const messageKey = contract.status === 'loading' ? 'workflow.nodeLibrary.states.loading'
    : contract.status === 'error' ? 'workflow.nodeLibrary.states.error'
      : contract.status === 'empty' ? 'workflow.nodeLibrary.states.empty'
        : contract.status === 'mismatch' ? 'workflow.nodeLibrary.states.contractMismatch'
          : undefined

  return (
    <div className="flex-1">
      <Tabs defaultValue="nodes" className="w-full">
        <TabsList className="w-full">
          <TabsTrigger value="nodes" className="flex-1">{t('workflow.nodeLibrary.tabs.nodes')}</TabsTrigger>
          <TabsTrigger value="templates" className="flex-1">{t('workflow.nodeLibrary.tabs.templates')}</TabsTrigger>
        </TabsList>
        <TabsContent value="nodes" className="mt-2">
          <ScrollArea className="h-full">
            {messageKey ? (
              <div role="status" className="m-1 rounded-md border border-amber-500/50 bg-amber-500/10 p-3 text-sm">
                {t(messageKey as TranslationKey)}
              </div>
            ) : (
              <div className="space-y-4 p-1">
                {nodeCategories.map((category) => {
                  const capabilities = contract.status === 'ready'
                    ? contract.capabilities.filter((capability) => capability.category === category.id)
                    : []
                  if (!capabilities.length) return null
                  const firstNodeType = capabilities[0].ui_type as CanonicalBuilderType
                  const icon = getIconComponent(nodeTypeInfo[firstNodeType].icon)
                  return (
                    <div key={category.id} className="space-y-2">
                      <div className="flex items-center gap-1.5">
                        {icon}
                        <h3 className="text-sm font-medium">
                          {t(`workflow.nodeLibrary.categories.${category.id}` as TranslationKey)}
                        </h3>
                      </div>
                      <div className="grid grid-cols-1 gap-2">
                        {capabilities.map((capability) => {
                          const nodeType = capability.ui_type as CanonicalBuilderType
                          const info = nodeTypeInfo[nodeType]
                          const label = t(`workflow.nodeLibrary.items.${nodeType}.label` as TranslationKey)
                          const description = info.descriptionKey
                            ? t(info.descriptionKey as TranslationKey)
                            : info.description
                          return (
                            <button
                              type="button"
                              key={nodeType}
                              className="flex w-full cursor-grab flex-col rounded-md border bg-card p-2 text-left transition-colors hover:border-primary"
                              draggable
                              onDragStart={(event) => onDragStart(event, nodeType, label)}
                              onClick={() => addNewNode(nodeType, label)}
                            >
                              <div className="text-sm font-medium">{label}</div>
                              <div className="text-xs text-muted-foreground">{description}</div>
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </ScrollArea>
        </TabsContent>
        <TabsContent value="templates" className="mt-2">
          <div className="space-y-2 p-1">
            <Button
              type="button"
              variant="outline"
              className="h-auto w-full justify-start gap-3 rounded-md border bg-card p-3 text-left shadow-none"
              disabled={!onCreateTicketTemplate || creatingTicketTemplate}
              onClick={onCreateTicketTemplate}
            >
              <TicketCheck className="h-4 w-4 shrink-0 text-primary" />
              <span className="min-w-0">
                <span className="block text-sm font-medium">{t('workflow.nodeLibrary.templates.ticketTriage.title')}</span>
                <span className="block whitespace-normal text-xs text-muted-foreground">{t('workflow.nodeLibrary.templates.ticketTriage.description')}</span>
              </span>
            </Button>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default NodeLibraryPanel
