import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { DrawerClose, DrawerDescription, DrawerFooter, DrawerHeader, DrawerTitle } from '@/components/ui/drawer'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useDrawer } from '@/hooks/use-drawer'
import { useToast } from '@/hooks/use-toast'
import { useTranslation } from '@/i18n'

const ProviderKindOptions = [
  { label: 'OpenAI', value: 'openai' },
  { label: 'Anthropic', value: 'anthropic' },
  { label: 'Gemini', value: 'gemini' },
  { label: 'OpenAI Compatible', value: 'openai_compat' },
]

const ProviderStatusOptions = [
  { label: 'active', value: 'active' },
  { label: 'disabled', value: 'disabled' },
  { label: 'error', value: 'error' },
]

export type SettingSheetProps = {
  item?: any
  index: number
  onSave?: (data: any) => void
}

export function SettingSheet(props: SettingSheetProps) {
  const { item = {}, onSave } = props
  const { t } = useTranslation()
  const drawer = useDrawer()
  const { toast } = useToast()
  const [activeTab, setActiveTab] = useState('general')
  const [formData, setFormData] = useState({
    name: item.name || '',
    kind: item.kind || 'openai',
    baseUrl: item.baseUrl || '',
    credentialRef: item.credentialRef || '',
    status: item.status || 'active',
    syncPolicy: item.syncPolicy || {
      auto_sync: false,
      interval_minutes: 360,
      recreate_deleted: false,
      default_enabled: true,
    },
  })

  const handleInputChange = (field: string, value: any) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }))
  }

  const handleSyncPolicyChange = (field: string, value: any) => {
    setFormData(prev => ({
      ...prev,
      syncPolicy: {
        ...prev.syncPolicy,
        [field]: value
      }
    }))
  }

  const handleSave = async () => {
    try {
      onSave?.(formData)
      toast({
        title: t('system.model.providerSettings.actions.saveSuccessTitle'),
        description: t('system.model.providerSettings.actions.saveSuccessDescription'),
      })
      drawer.close()
    } catch (error) {
      console.error('Failed to save provider:', error)
      toast({
        title: t('system.model.providerSettings.actions.saveFailedTitle'),
        description: t('system.model.providerSettings.actions.saveFailedDescription'),
        type: 'error',
      })
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto">
        <DrawerHeader>
          <DrawerTitle className="text-sm font-bold">{t('system.model.providerSettings.title')}</DrawerTitle>
          <DrawerDescription>
            {t('system.model.providerSettings.description')}
          </DrawerDescription>
        </DrawerHeader>

        <div className="p-4">
          <Tabs defaultValue="general" className="w-full" onValueChange={setActiveTab}>
            <TabsList className="grid w-full grid-cols-3 mb-6">
              <TabsTrigger value="general">{t('system.model.providerSettings.tabs.general')}</TabsTrigger>
              <TabsTrigger value="api">{t('system.model.providerSettings.tabs.api')}</TabsTrigger>
              <TabsTrigger value="advanced">{t('system.model.providerSettings.tabs.advanced')}</TabsTrigger>
            </TabsList>

            <TabsContent value="general" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>{t('system.model.providerSettings.sections.basicInfo.title')}</CardTitle>
                  <CardDescription>{t('system.model.providerSettings.sections.basicInfo.description')}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Label>{t('system.model.providerSettings.fields.name')}</Label>
                    <Input
                      placeholder={t('system.model.providerSettings.fields.namePlaceholder')}
                      value={formData.name}
                      onChange={(e) => handleInputChange('name', e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>{t('system.model.providerSettings.fields.type')}</Label>
                    <Select
                      value={formData.kind}
                      onValueChange={(value) => handleInputChange('kind', value)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder={t('system.model.providerSettings.fields.typePlaceholder')} />
                      </SelectTrigger>
                      <SelectContent>
                        {ProviderKindOptions.map(option => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>{t('system.model.providerSettings.fields.status')}</Label>
                    <Select
                      value={formData.status}
                      onValueChange={(value) => handleInputChange('status', value)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder={t('system.model.providerSettings.fields.statusPlaceholder')} />
                      </SelectTrigger>
                      <SelectContent>
                        {ProviderStatusOptions.map(option => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="api" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>{t('system.model.providerSettings.sections.api.title')}</CardTitle>
                  <CardDescription>{t('system.model.providerSettings.sections.api.description')}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Label>{t('system.model.providerSettings.fields.apiEndpoint')}</Label>
                    <Input
                      placeholder="https://api.example.com/v1"
                      value={formData.baseUrl}
                      onChange={(e) => handleInputChange('baseUrl', e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>{t('system.model.providerSettings.fields.apiKey')}</Label>
                    <Input
                      type="text"
                      placeholder={t('system.model.providerSettings.fields.apiKeyPlaceholder')}
                      value={formData.credentialRef}
                      onChange={(e) => handleInputChange('credentialRef', e.target.value)}
                    />
                    <p className="text-xs text-muted-foreground">
                      {t('system.model.providerSettings.fields.apiKeyPlaceholder')}
                    </p>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="advanced" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>{t('system.model.providerSettings.sections.advanced.title')}</CardTitle>
                  <CardDescription>{t('system.model.providerSettings.sections.advanced.description')}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label>{t('system.model.providerSettings.fields.performanceMonitoring')}</Label>
                      <p className="text-sm text-muted-foreground">
                        {t('system.model.providerSettings.fields.performanceMonitoringHint')}
                      </p>
                    </div>
                    <Switch
                      checked={formData.syncPolicy.auto_sync}
                      onCheckedChange={(checked) => handleSyncPolicyChange('auto_sync', checked)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>{t('system.model.providerSettings.fields.timeoutSeconds')}</Label>
                    <Input
                      type="number"
                      value={formData.syncPolicy.interval_minutes}
                      onChange={(e) => handleSyncPolicyChange('interval_minutes', parseInt(e.target.value, 10))}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label>{t('system.model.providerSettings.fields.requestSigning')}</Label>
                      <p className="text-sm text-muted-foreground">
                        {t('system.model.providerSettings.fields.requestSigningHint')}
                      </p>
                    </div>
                    <Switch
                      checked={formData.syncPolicy.recreate_deleted}
                      onCheckedChange={(checked) => handleSyncPolicyChange('recreate_deleted', checked)}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label>{t('system.model.providerSettings.fields.ipWhitelist')}</Label>
                      <p className="text-sm text-muted-foreground">
                        {t('system.model.providerSettings.fields.ipWhitelistHint')}
                      </p>
                    </div>
                    <Switch
                      checked={formData.syncPolicy.default_enabled}
                      onCheckedChange={(checked) => handleSyncPolicyChange('default_enabled', checked)}
                    />
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </div>

      <DrawerFooter className="border-t flex-col gap-4">
        <div className="w-full flex justify-between gap-4">
          <DrawerClose asChild className="flex-1">
            <Button variant="outline">{t('common.operation.cancel')}</Button>
          </DrawerClose>
          <Button className="flex-1" onClick={handleSave}>{t('system.model.providerSettings.actions.saveChanges')}</Button>
        </div>
      </DrawerFooter>
    </div>
  )
}

export default SettingSheet
