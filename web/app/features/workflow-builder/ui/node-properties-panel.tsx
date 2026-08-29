import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Slider } from '@/components/ui/slider'
import { Settings, Code } from 'lucide-react'
import type { Node } from '@xyflow/react'
import { propertyPanels } from './nodes'
import { cn } from '@/lib/utils'
import { useTranslation } from '@/i18n'

interface NodePropertiesPanelProps {
  selectedNode: Node | null
  updateNodeData: (nodeId: string, data: any) => void
  onNodeValidityChange?: (nodeId: string, valid: boolean) => void
  className?: string
}

const NodePropertiesPanel: React.FC<NodePropertiesPanelProps> = ({
  selectedNode,
  updateNodeData,
  onNodeValidityChange,
  className
}) => {
  const { t } = useTranslation()
  const selectedNodeId = selectedNode?.id
  const handleValidityChange = React.useCallback((valid: boolean) => {
    if (selectedNodeId) onNodeValidityChange?.(selectedNodeId, valid)
  }, [onNodeValidityChange, selectedNodeId])
  if (!selectedNode) {
    return (
      <Card className="w-full h-full border-none shadow-none">
        <CardContent className="p-6 flex flex-col items-center justify-center h-full">
          <div className="text-muted-foreground text-center">
            <Settings className="h-10 w-10 mx-auto mb-4 opacity-20" />
            <p>{t('workflow.nodeProperties.empty')}</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (selectedNode.type === 'compatibility-node') {
    const formatJson = (value: unknown) => {
      const formatted = JSON.stringify(value, null, 2)
      return formatted === undefined ? t('workflow.nodeProperties.compatibility.unavailable') : formatted
    }
    return (
      <Card className={cn('w-full border-none shadow-none', className)}>
        <CardHeader className="border-b px-4 py-3">
          <CardTitle className="text-base font-medium">{t('workflow.nodeProperties.compatibility.title')}</CardTitle>
          <CardDescription>{t('workflow.nodeProperties.compatibility.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 p-4">
          <div className="space-y-2">
            <Label>{t('workflow.nodeProperties.compatibility.runtimeType')}</Label>
            <div className="rounded-md bg-muted p-2 font-mono text-xs">
              {String(selectedNode.data.originalRuntimeType)}
            </div>
          </div>
          <div className="space-y-2">
            <Label>{t('workflow.nodeProperties.compatibility.params')}</Label>
            <pre className="max-h-52 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-3 text-xs">
              {formatJson(selectedNode.data.originalParams)}
            </pre>
          </div>
          <div className="space-y-2">
            <Label>{t('workflow.nodeProperties.compatibility.ui')}</Label>
            <pre className="max-h-52 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-3 text-xs">
              {formatJson(selectedNode.data.originalUi)}
            </pre>
          </div>
        </CardContent>
      </Card>
    )
  }

  const handleDataChange = (data: any) => {
    updateNodeData(selectedNode.id, data)
  }

  return (
    <Card className={cn("w-full border-none shadow-none", className)}>
      <CardHeader className="px-4 py-3 border-b">
        <CardTitle className="text-base font-medium flex items-center">
          <span className="flex-1">{selectedNode.data.label as string || t('workflow.nodeProperties.unnamed')}</span>
          <span className="text-xs px-2 py-0.5 bg-muted text-muted-foreground rounded">
            {selectedNode.type}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <Tabs defaultValue="properties" className="w-full">
          <TabsList className="w-full rounded-none border-b bg-transparent h-10">
            <TabsTrigger value="properties" className="flex-1 data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none">
              {t('workflow.nodeProperties.tabs.properties')}
            </TabsTrigger>
            <TabsTrigger value="advanced" className="flex-1 data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none">
              {t('workflow.nodeProperties.tabs.advanced')}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="properties" className="mt-0">
            <ScrollArea className="h-[calc(100vh-220px)]">
              <div className="p-4">
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="node-name">{t('workflow.nodeProperties.name')}</Label>
                    <Input
                      id="node-name"
                      value={selectedNode.data.label as string || ''}
                      onChange={(e) => handleDataChange({ label: e.target.value })}
                    />
                  </div>

                  {(() => {
                    const PropertyPanel = propertyPanels[selectedNode.type as keyof typeof propertyPanels]
                    if (PropertyPanel) {
                      return (
                        <PropertyPanel
                          data={selectedNode.data}
                          onChange={handleDataChange}
                          onValidityChange={handleValidityChange}
                        />
                      )
                    } else {
                      return (
                        <div className="p-4 text-center text-muted-foreground">
                          {t('workflow.nodeProperties.noPanel')}
                        </div>
                      )
                    }
                  })()}
                </div>
              </div>
            </ScrollArea>
          </TabsContent>

          <TabsContent value="advanced" className="mt-0">
            <ScrollArea className="h-[calc(100vh-220px)]">
              <div className="p-4 space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="node-cache">{t('workflow.nodeProperties.cache')}</Label>
                    <Switch
                      id="node-cache"
                      checked={selectedNode.data.cache as boolean || false}
                      onCheckedChange={(checked) => handleDataChange({ cache: checked })}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">{t('workflow.nodeProperties.cacheTip')}</p>
                </div>

                <div className="space-y-2">
                  <Label>{t('workflow.nodeProperties.timeout')}</Label>
                  <div className="flex items-center space-x-2">
                    <Slider
                      defaultValue={[selectedNode.data.timeout as number || 30]}
                      max={120}
                      step={1}
                      onValueChange={(value) => handleDataChange({ timeout: Array.isArray(value) ? value[0] : value })}
                      className="flex-1"
                    />
                    <span className="w-12 text-center text-sm">
                      {selectedNode.data.timeout as number || 30}s
                    </span>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="node-id">{t('workflow.nodeProperties.nodeId')}</Label>
                  <div className="flex items-center space-x-2">
                    <Input
                      id="node-id"
                      value={selectedNode.id}
                      readOnly
                      className="font-mono text-xs"
                    />
                    <button className="p-2 hover:bg-muted rounded">
                      <Code className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </div>
            </ScrollArea>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}

export default NodePropertiesPanel
