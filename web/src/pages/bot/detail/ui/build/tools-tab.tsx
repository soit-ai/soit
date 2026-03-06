import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { PlusCircle, Globe, InfoIcon } from 'lucide-react'
import { useTranslation } from '@/i18n'

interface ToolsTabProps {
  enableTools: boolean
  setEnableTools: (enabled: boolean) => void
  availableTools: Array<{
    id: string,
    name: string,
    description: string,
    category: string,
    icon: React.ReactNode
  }>
  selectedTools: string[]
  handleToolSelect: (toolId: string) => void
  handleCreateTool: () => void
}

export const ToolsTab: React.FC<ToolsTabProps> = ({
  enableTools,
  setEnableTools,
  availableTools,
  selectedTools,
  handleToolSelect,
  handleCreateTool
}) => {
  const { t } = useTranslation()

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>{t('bot.build.tools.title')}</CardTitle>
          <Switch 
            checked={enableTools} 
            onCheckedChange={setEnableTools} 
          />
        </div>
        <CardDescription>{t('bot.build.tools.description')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {enableTools ? (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-sm font-medium">{t('bot.build.tools.selectedCount', { count: selectedTools.length })}</h3>
              <div className="flex space-x-2">
                <Button variant="outline" size="sm">
                  <Globe className="mr-2 h-4 w-4" />
                  {t('bot.build.tools.connectApi')}
                </Button>
                <Button variant="outline" size="sm" onClick={handleCreateTool}>
                  <PlusCircle className="mr-2 h-4 w-4" />
                  {t('bot.build.tools.createTool')}
                </Button>
              </div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {availableTools.map((tool) => (
                <div 
                  key={tool.id} 
                  className={`flex items-start space-x-4 rounded-md border p-4 cursor-pointer ${
                    selectedTools.includes(tool.id) ? 'border-primary bg-primary/5' : ''
                  }`}
                  onClick={() => handleToolSelect(tool.id)}
                >
                  <div className="p-2 rounded-full bg-primary/10">
                    {tool.icon}
                  </div>
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <h4 className="font-medium">{tool.name}</h4>
                        <Badge variant="outline">{tool.category}</Badge>
                      </div>
                      <Switch 
                        checked={selectedTools.includes(tool.id)} 
                        onCheckedChange={handleToolSelect.bind(null, tool.id)}
                        className="cursor-pointer"
                        onClick={(event) => {
                          // Prevent event bubbling so the card click handler does not fire.
                          event.stopPropagation();
                        }}
                      />
                    </div>
                    <p className="text-sm text-muted-foreground">{tool.description}</p>
                  </div>
                </div>
              ))}
            </div>
            
            {selectedTools.length > 0 && (
              <div className="rounded-md border p-4 bg-muted/30">
                <h4 className="font-medium mb-2">{t('bot.build.tools.settingsTitle')}</h4>
                <div className="space-y-3">
                  <div className="flex items-center space-x-2">
                    <Switch id="auto-tool-calling" defaultChecked />
                    <Label htmlFor="auto-tool-calling">{t('bot.build.tools.autoCalling')}</Label>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {t('bot.build.tools.autoCallingDescription')}
                  </p>
                  
                  <div className="space-y-2 pt-2 border-t">
                    <Label>{t('bot.build.tools.mode')}</Label>
                    <Select defaultValue="sequential">
                      <SelectTrigger>
                        <SelectValue placeholder={t('bot.build.tools.modePlaceholder')} />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="sequential">{t('bot.build.tools.modeOptions.sequential')}</SelectItem>
                        <SelectItem value="parallel">{t('bot.build.tools.modeOptions.parallel')}</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      {t('bot.build.tools.modeHint')}
                    </p>
                  </div>
                </div>
              </div>
            )}
            
            <div className="rounded-md border p-4 bg-blue-50 dark:bg-blue-950/50">
              <div className="flex items-start space-x-2">
                <InfoIcon className="h-5 w-5 text-blue-500 mt-0.5" />
                <div>
                  <h4 className="font-medium text-blue-700 dark:text-blue-300">{t('bot.build.tools.exampleTitle')}</h4>
                  <p className="text-sm text-blue-600 dark:text-blue-400 mt-1">
                    {t('bot.build.tools.exampleLead')}
                  </p>
                  <ol className="text-sm text-blue-600 dark:text-blue-400 mt-1 space-y-1 list-decimal list-inside">
                    <li>{t('bot.build.tools.exampleSteps.detect')}</li>
                    <li>{t('bot.build.tools.exampleSteps.invoke')}</li>
                    <li>{t('bot.build.tools.exampleSteps.params')}</li>
                    <li>{t('bot.build.tools.exampleSteps.receive')}</li>
                    <li>{t('bot.build.tools.exampleSteps.compose')}</li>
                  </ol>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center p-4">
            <p className="text-sm text-muted-foreground">{t('bot.build.tools.empty')}</p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default ToolsTab
