import React, { useEffect, useState } from 'react'
import { useTranslation } from '@/i18n'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Checkbox } from '@/components/ui/checkbox'
import { DownloadIcon, InfoIcon, ShieldAlertIcon, ShieldCheckIcon, ShieldIcon } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { useNavLayout } from '@/components/layout/nav-layout'

// Guardrail configuration item
interface GuardrailItemProps {
  title: string
  description: string
  enabled: boolean
  onToggle: (value: boolean) => void
  children?: React.ReactNode
  icon?: React.ComponentType<any>
}

const GuardrailItem = ({
  title,
  description,
  enabled,
  onToggle,
  children,
  icon: Icon = ShieldIcon,
}: GuardrailItemProps) => {
  return (
    <Card className="mb-4">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon className="h-5 w-5 text-primary" />
            <CardTitle className="text-lg">{title}</CardTitle>
          </div>
          <Switch checked={enabled} onCheckedChange={onToggle} />
        </div>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      {enabled && children && (
        <>
          <Separator className="mb-3" />
          <CardContent>{children}</CardContent>
        </>
      )}
    </Card>
  )
}

interface SafetyGuardrailProps {
  subTab?: string | null
}

function BoxHeader({
  title,
  description,
  onExport,
  exportLabel,
}: {
  title: string
  description: string
  onExport?: () => void
  exportLabel?: string
}) {
  return (
    <div className="flex flex-1 justify-between">
      <div>
        <h3 className="text-lg font-bold">{title}</h3>
        <p className="text-sm text-muted-foreground mt-1">{description}</p>
      </div>
      <div>
        {onExport && (
          <Button variant="outline" size="sm" onClick={onExport}>
            <DownloadIcon className="h-4 w-4 mr-2" />
            {exportLabel}
          </Button>
        )}
      </div>
    </div>
  )
}

export function SafetyGuardrail({ subTab = null }: SafetyGuardrailProps) {
  const { t } = useTranslation()
  const { setHeaderContent } = useNavLayout()
  const [guardrails, setGuardrails] = useState({
    contentFilter: {
      enabled: true,
      level: 75,
    },
    harmfulContent: {
      enabled: true,
    },
    sensitiveTopics: {
      enabled: true,
      topics: {
        politics: true,
        religion: true,
        violence: true,
        selfHarm: true,
        sexualContent: true,
        discrimination: true,
      },
    },
    privacyProtection: {
      enabled: true,
      piiDetection: true,
      piiMasking: true,
    },
    outputValidation: {
      enabled: false,
    },
  })

  useEffect(() => {
    setHeaderContent(
      <BoxHeader
        title={t('safe.safetyGuardrail.header.title')}
        description={t('safe.safetyGuardrail.header.description')}
        exportLabel={t('safe.safetyGuardrail.header.export')}
        onExport={() => console.log('Exporting guardrail configuration...')}
      />
    )
    return () => setHeaderContent(null)
  }, [setHeaderContent, t])

  const updateGuardrail = (path: string, value: any) => {
    const newGuardrails = { ...guardrails }
    const pathParts = path.split('.')

    let current: any = newGuardrails
    for (let i = 0; i < pathParts.length - 1; i += 1) {
      current = current[pathParts[i]]
    }

    current[pathParts[pathParts.length - 1]] = value
    setGuardrails(newGuardrails)
  }

  const getTopicLabel = (topic: string) =>
    t(`safe.safetyGuardrail.topics.${topic}`, { defaultValue: topic })

  const renderSubTabContent = () => {
    switch (subTab) {
      case 'content-filter':
        return (
          <Card className="w-full">
            <CardHeader>
              <CardTitle>{t('safe.safetyGuardrail.subTabs.contentFilter.title')}</CardTitle>
              <CardDescription>{t('safe.safetyGuardrail.subTabs.contentFilter.description')}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>{t('safe.safetyGuardrail.subTabs.contentFilter.strengthLabel')}</Label>
                  <Slider
                    value={[guardrails.contentFilter.level]}
                    onValueChange={(value) => updateGuardrail('contentFilter.level', value[0])}
                    max={100}
                    step={1}
                  />
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>{t('safe.safetyGuardrail.subTabs.contentFilter.strengthScale.lenient')}</span>
                    <span>{t('safe.safetyGuardrail.subTabs.contentFilter.strengthScale.balanced')}</span>
                    <span>{t('safe.safetyGuardrail.subTabs.contentFilter.strengthScale.strict')}</span>
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>{t('safe.safetyGuardrail.subTabs.contentFilter.autoDetect')}</Label>
                    <Switch
                      checked={guardrails.contentFilter.enabled}
                      onCheckedChange={(value) => updateGuardrail('contentFilter.enabled', value)}
                    />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )
      case 'harmful-content':
        return (
          <Card className="w-full">
            <CardHeader>
              <CardTitle>{t('safe.safetyGuardrail.subTabs.harmfulContent.title')}</CardTitle>
              <CardDescription>{t('safe.safetyGuardrail.subTabs.harmfulContent.description')}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <Label>{t('safe.safetyGuardrail.subTabs.harmfulContent.enable')}</Label>
                  <Switch
                    checked={guardrails.harmfulContent.enabled}
                    onCheckedChange={(value) => updateGuardrail('harmfulContent.enabled', value)}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        )
      case 'sensitive-topics':
        return (
          <Card className="w-full">
            <CardHeader>
              <CardTitle>{t('safe.safetyGuardrail.subTabs.sensitiveTopics.title')}</CardTitle>
              <CardDescription>{t('safe.safetyGuardrail.subTabs.sensitiveTopics.description')}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <Label>{t('safe.safetyGuardrail.subTabs.sensitiveTopics.enable')}</Label>
                  <Switch
                    checked={guardrails.sensitiveTopics.enabled}
                    onCheckedChange={(value) => updateGuardrail('sensitiveTopics.enabled', value)}
                  />
                </div>
                <Separator />
                <div className="space-y-2">
                  <Label>{t('safe.safetyGuardrail.subTabs.sensitiveTopics.categoriesLabel')}</Label>
                  <div className="grid grid-cols-2 gap-2">
                    {Object.entries(guardrails.sensitiveTopics.topics).map(([key, value]) => (
                      <div key={key} className="flex items-center space-x-2">
                        <Checkbox
                          id={key}
                          checked={value as boolean}
                          onCheckedChange={(checked: boolean | 'indeterminate') =>
                            updateGuardrail(`sensitiveTopics.topics.${key}`, Boolean(checked))
                          }
                        />
                        <Label htmlFor={key}>{getTopicLabel(key)}</Label>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )
      default:
        return null
    }
  }

  if (subTab) {
    return <div className="space-y-4">{renderSubTabContent()}</div>
  }

  return (
    <div className="space-y-4">
      <GuardrailItem
        title={t('safe.safetyGuardrail.cards.contentFilter.title')}
        description={t('safe.safetyGuardrail.cards.contentFilter.description')}
        enabled={guardrails.contentFilter.enabled}
        onToggle={(value) => updateGuardrail('contentFilter.enabled', value)}
        icon={ShieldCheckIcon}
      >
        <div className="space-y-4">
          <div>
            <div className="flex justify-between mb-2">
              <Label>{t('safe.safetyGuardrail.cards.contentFilter.strengthLabel')}</Label>
              <span className="text-sm text-muted-foreground">{guardrails.contentFilter.level}%</span>
            </div>
            <Slider
              value={[guardrails.contentFilter.level]}
              min={0}
              max={100}
              step={1}
              onValueChange={(value) => updateGuardrail('contentFilter.level', value[0])}
            />
            <div className="flex justify-between mt-1">
              <span className="text-xs text-muted-foreground">
                {t('safe.safetyGuardrail.cards.contentFilter.minLabel')}
              </span>
              <span className="text-xs text-muted-foreground">
                {t('safe.safetyGuardrail.cards.contentFilter.maxLabel')}
              </span>
            </div>
          </div>
        </div>
      </GuardrailItem>

      <GuardrailItem
        title={t('safe.safetyGuardrail.cards.harmfulContent.title')}
        description={t('safe.safetyGuardrail.cards.harmfulContent.description')}
        enabled={guardrails.harmfulContent.enabled}
        onToggle={(value) => updateGuardrail('harmfulContent.enabled', value)}
        icon={ShieldAlertIcon}
      />

      <GuardrailItem
        title={t('safe.safetyGuardrail.cards.sensitiveTopics.title')}
        description={t('safe.safetyGuardrail.cards.sensitiveTopics.description')}
        enabled={guardrails.sensitiveTopics.enabled}
        onToggle={(value) => updateGuardrail('sensitiveTopics.enabled', value)}
      >
        <div className="grid grid-cols-2 gap-4">
          {Object.entries(guardrails.sensitiveTopics.topics).map(([topic, enabled]) => (
            <div key={topic} className="flex items-center space-x-2">
              <Switch
                id={`topic-${topic}`}
                checked={enabled}
                onCheckedChange={(value) => updateGuardrail(`sensitiveTopics.topics.${topic}`, value)}
              />
              <Label htmlFor={`topic-${topic}`}>{getTopicLabel(topic)}</Label>
            </div>
          ))}
        </div>
      </GuardrailItem>

      <GuardrailItem
        title={t('safe.safetyGuardrail.cards.privacyProtection.title')}
        description={t('safe.safetyGuardrail.cards.privacyProtection.description')}
        enabled={guardrails.privacyProtection.enabled}
        onToggle={(value) => updateGuardrail('privacyProtection.enabled', value)}
      >
        <div className="space-y-4">
          <div className="flex items-center space-x-2">
            <Switch
              id="pii-detection"
              checked={guardrails.privacyProtection.piiDetection}
              onCheckedChange={(value) => updateGuardrail('privacyProtection.piiDetection', value)}
            />
            <div className="flex items-center">
              <Label htmlFor="pii-detection">{t('safe.safetyGuardrail.privacy.piiDetection.label')}</Label>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <InfoIcon className="h-4 w-4 ml-1 text-muted-foreground" />
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>{t('safe.safetyGuardrail.privacy.piiDetection.hint')}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <Switch
              id="pii-masking"
              checked={guardrails.privacyProtection.piiMasking}
              onCheckedChange={(value) => updateGuardrail('privacyProtection.piiMasking', value)}
            />
            <div className="flex items-center">
              <Label htmlFor="pii-masking">{t('safe.safetyGuardrail.privacy.piiMasking.label')}</Label>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <InfoIcon className="h-4 w-4 ml-1 text-muted-foreground" />
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>{t('safe.safetyGuardrail.privacy.piiMasking.hint')}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </div>
        </div>
      </GuardrailItem>

      <GuardrailItem
        title={t('safe.safetyGuardrail.cards.outputValidation.title')}
        description={t('safe.safetyGuardrail.cards.outputValidation.description')}
        enabled={guardrails.outputValidation.enabled}
        onToggle={(value) => updateGuardrail('outputValidation.enabled', value)}
      />

      <CardFooter className="flex justify-end gap-2 pt-4">
        <Button variant="outline">{t('safe.safetyGuardrail.actions.reset')}</Button>
        <Button>{t('safe.safetyGuardrail.actions.save')}</Button>
      </CardFooter>
    </div>
  )
}
