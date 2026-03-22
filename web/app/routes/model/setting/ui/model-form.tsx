import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { DrawerClose, DrawerDescription, DrawerFooter, DrawerHeader, DrawerTitle } from '@/components/ui/drawer'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { ModelConfig, ModelFormProps } from './types'
import { MODEL_CAPABILITIES } from './types'
import { useTranslation } from '@/i18n'

export function ModelForm({ model, onSave, onCancel, onChange, title }: ModelFormProps) {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState('basic')
  const [formData, setFormData] = useState<ModelConfig>(model)
  const resolvedTitle = title ?? t('system.model.form.title')

  const handleInputChange = (field: keyof ModelConfig, value: any) => {
    const newData = { ...formData, [field]: value }
    setFormData(newData)
    onChange(newData)
  }

  const handleCapabilityChange = (capability: string, checked: boolean) => {
    const capabilities = formData.capabilities || []
    const newCapabilities = checked
      ? [...capabilities, capability]
      : capabilities.filter(c => c !== capability)
    
    handleInputChange('capabilities', newCapabilities)
  }

  return (
    <form className="h-full flex flex-col">
      <DrawerHeader>
        <DrawerTitle className="text-sm font-bold">{resolvedTitle}</DrawerTitle>
        <DrawerDescription>
          {t('system.model.form.description')}
        </DrawerDescription>
      </DrawerHeader>

      <div className="flex-1 overflow-y-auto p-4">
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="w-full">
            <TabsTrigger value="basic" className="flex-1">{t('system.model.form.tabs.basic')}</TabsTrigger>
            <TabsTrigger value="advanced" className="flex-1">{t('system.model.form.tabs.advanced')}</TabsTrigger>
          </TabsList>

          <TabsContent value="basic" className="mt-4 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t('system.model.form.sections.basicInfo.title')}</CardTitle>
                <CardDescription>{t('system.model.form.sections.basicInfo.description')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>{t('system.model.form.fields.modelName')}</Label>
                  <Input 
                    placeholder={t('system.model.form.fields.modelNamePlaceholder')}
                    value={formData.modelId}
                    onChange={(e) => handleInputChange('modelId', e.target.value)}
                    disabled={formData.source === 'platform'}
                  />
                </div>
                <div className="space-y-2">
                  <Label>{t('system.model.form.fields.name')}</Label>
                  <Input 
                    placeholder={t('system.model.form.fields.namePlaceholder')}
                    value={formData.displayName || ''}
                    onChange={(e) => handleInputChange('displayName', e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>{t('system.model.form.fields.description')}</Label>
                  <Textarea 
                    placeholder={t('system.model.form.fields.descriptionPlaceholder')}
                    value={formData.description}
                    onChange={(e) => handleInputChange('description', e.target.value)}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>{t('system.model.form.fields.status')}</Label>
                    <p className="text-sm text-muted-foreground">{t('system.model.form.fields.statusHint')}</p>
                  </div>
                  <Switch 
                    checked={formData.enabled}
                    onCheckedChange={(checked) => handleInputChange('enabled', checked)}
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t('system.model.form.sections.capabilities.title')}</CardTitle>
                <CardDescription>{t('system.model.form.sections.capabilities.description')}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4">
                  {MODEL_CAPABILITIES.map(cap => (
                    <div key={cap.value} className="flex items-center space-x-2">
                      <Switch
                        checked={formData.capabilities?.includes(cap.value) || false}
                        onCheckedChange={(checked) => handleCapabilityChange(cap.value, checked)}
                      />
                      <div className="space-y-0.5">
                        <Label>{t(cap.labelKey)}</Label>
                        <p className="text-sm text-muted-foreground">{t(cap.descriptionKey)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="advanced" className="mt-4 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t('system.model.form.sections.advanced.title')}</CardTitle>
                <CardDescription>{t('system.model.form.sections.advanced.description')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>{t('system.model.form.fields.maxTokens')}</Label>
                  <Input 
                    type="number"
                    placeholder={t('system.model.form.fields.maxTokensPlaceholder')}
                    value={formData.maxOutputTokens ?? ''}
                    onChange={(e) => handleInputChange('maxOutputTokens', parseInt(e.target.value))}
                  />
                </div>
                <div className="space-y-2">
                  <Label>{t('system.model.form.fields.contextLength')}</Label>
                  <Input 
                    type="number"
                    placeholder={t('system.model.form.fields.contextLengthPlaceholder')}
                    value={formData.contextWindow ?? ''}
                    onChange={(e) => handleInputChange('contextWindow', parseInt(e.target.value))}
                  />
                </div>
                <div className="space-y-2">
                  <Label>{t('system.model.form.fields.modelType')}</Label>
                  <Input 
                    placeholder={t('system.model.form.fields.modelTypePlaceholder')}
                    value={formData.lifecycle || ''}
                    onChange={(e) => handleInputChange('lifecycle', e.target.value)}
                  />
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      <DrawerFooter className="border-t">
        <div className="flex justify-between gap-4">
          <DrawerClose asChild>
            <Button variant="outline" onClick={onCancel}>
              {t('common.operation.cancel')}
            </Button>
          </DrawerClose>
          <Button onClick={(e) => {
            e.preventDefault()
            onSave(e)
          }}>
            {t('common.operation.save')}
          </Button>
        </div>
      </DrawerFooter>
    </form>
  )
}
