import React from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import { MessageSquare, Cpu, Wrench, Database, BotMessageSquare, Workflow, TicketCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { nodeCategories, nodeTypeInfo } from './nodes'
import { useTranslation } from '@/i18n'
import type { TranslationKey } from '@/i18n/types'

interface NodeLibraryPanelProps {
  onDragStart: (event: React.DragEvent<HTMLDivElement>, nodeType: string, nodeLabel: string) => void
  addNewNode: (type: string, label: string) => void
  onCreateTicketTemplate?: () => void
  creatingTicketTemplate?: boolean
}

const NodeLibraryPanel: React.FC<NodeLibraryPanelProps> = ({
  onDragStart,
  addNewNode,
  onCreateTicketTemplate,
  creatingTicketTemplate = false,
}) => {
  const { t } = useTranslation()
  const getIconComponent = (iconName: string) => {
    switch(iconName) {
      case 'MessageSquare':
        return <MessageSquare className="h-4 w-4" />;
      case 'Cpu':
        return <Cpu className="h-4 w-4" />;
      case 'Wrench':
        return <Wrench className="h-4 w-4" />;
      case 'Database':
        return <Database className="h-4 w-4" />;
      case 'BotMessageSquare':
        return <BotMessageSquare className="h-4 w-4" />;
      default:
        return <Workflow className="h-4 w-4" />;
    }
  };

  const getNodeLabel = (info: any) => {
    if (info.labelKey) {
      return t(info.labelKey)
    }
    return info.label
  }

  const getNodeDescription = (info: any) => {
    if (info.descriptionKey) {
      return t(info.descriptionKey)
    }
    return info.description
  }

  return (
    <div className="flex-1">
      <Tabs defaultValue="nodes" className="w-full">
        <TabsList className="w-full">
          <TabsTrigger value="nodes" className="flex-1">{t('workflow.nodeLibrary.tabs.nodes')}</TabsTrigger>
          <TabsTrigger value="templates" className="flex-1">{t('workflow.nodeLibrary.tabs.templates')}</TabsTrigger>
        </TabsList>
        <TabsContent value="nodes" className="mt-2">
          <ScrollArea className="h-full">
            <div className="space-y-4 p-1">
              {nodeCategories.map((category) => {
                const firstNodeType = category.types[0];
                const firstNodeInfo = nodeTypeInfo[firstNodeType as keyof typeof nodeTypeInfo];
                const icon = getIconComponent(firstNodeInfo.icon);
                const categoryLabel = t(`workflow.nodeLibrary.categories.${category.id}` as TranslationKey)
                
                return (
                  <div key={category.id} className="space-y-2">
                    <div className="flex items-center gap-1.5">
                      {icon}
                      <h3 className="text-sm font-medium">{categoryLabel}</h3>
                    </div>
                    <div className="grid grid-cols-1 gap-2">
                      {category.types.map((nodeType) => {
                        const info = nodeTypeInfo[nodeType as keyof typeof nodeTypeInfo];
                        const label = getNodeLabel(info)
                        const description = getNodeDescription(info)
                        return (
                          <div
                            key={nodeType}
                            className="flex flex-col p-2 border rounded-md cursor-grab bg-card hover:border-primary transition-colors"
                            draggable
                            onDragStart={(e) => onDragStart(e, nodeType, label)}
                            onClick={() => addNewNode(nodeType, label)}
                          >
                            <div className="text-sm font-medium">{label}</div>
                            <div className="text-xs text-muted-foreground">{description}</div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
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
