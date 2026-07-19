import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Plus, RefreshCw, HeartPulse, ListChecks } from 'lucide-react'
import { useDrawer } from '@/hooks/use-drawer'
import { DrawerClose, DrawerDescription, DrawerFooter, DrawerHeader, DrawerTitle } from '@/components/ui/drawer'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { SettingSheet } from '../index'
import {
  listProviders,
  createProvider,
  updateProvider,
  deleteProvider,
  healthCheck,
  syncFromPlatform,
  listSyncJobs,
  getProviderSupportMatrix,
  type AdapterBackendSupport,
  type ProviderPreset,
  type ProviderSupportStatus,
} from '@/services/provider-service'
import { useToast } from '@/hooks/use-toast'
import { useTranslation } from '@/i18n'
import type { ProviderConfig } from './types'

// Provider kind enum
const ProviderKindEnum = {
  OPENAI: "openai",
  DEEPSEEK: "deepseek",
  ANTHROPIC: "anthropic",
  GEMINI: "gemini",
  OPENAI_COMPAT: "openai_compatible",
} as const

export interface ProviderListProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaveProvider: (provider: ProviderConfig) => void
  onDeleteProvider: (id: string) => void
  title?: string
}

export function ProviderList({ onSaveProvider, onDeleteProvider, title }: ProviderListProps) {
  const { t } = useTranslation()
  const drawer = useDrawer()
  const { toast } = useToast()
  const [providers, setProviders] = useState<ProviderConfig[]>([])
  const [supportMatrix, setSupportMatrix] = useState<ProviderSupportStatus[]>([])
  const [adapterBackends, setAdapterBackends] = useState<AdapterBackendSupport[]>([])
  const [providerPresets, setProviderPresets] = useState<ProviderPreset[]>([])
  const [loading, setLoading] = useState(true)
  const resolvedTitle = title ?? t('model.providerList.title')

  // Load providers
  useEffect(() => {
    loadProviders()
  }, [])

  const loadProviders = async () => {
    try {
      setLoading(true)
      const [data, support] = await Promise.all([
        listProviders(),
        getProviderSupportMatrix(),
      ])
      setProviders(data)
      setSupportMatrix(support.providers)
      setAdapterBackends(support.adapterBackends)
      setProviderPresets(support.providerPresets)
    } catch (error) {
      console.error('Failed to load providers:', error)
      toast({
        title: t('model.providerList.loadFailedTitle'),
        description: t('model.providerList.loadFailedDescription'),
        type: 'error',
      })
    } finally {
      setLoading(false)
    }
  }

  const handleSaveProvider = async (provider: ProviderConfig) => {
    try {
      let updatedProvider: ProviderConfig
      if (provider.id) {
        updatedProvider = await updateProvider(provider.id, provider)
      } else {
        updatedProvider = await createProvider(provider)
      }

      await loadProviders()

      onSaveProvider(updatedProvider)
      drawer.close()

      toast({
        title: t('model.providerList.saveSuccessTitle'),
        description: t('model.providerList.saveSuccessDescription'),
      })
    } catch (error) {
      console.error('Failed to save provider:', error)
      toast({
        title: t('model.providerList.saveFailedTitle'),
        description: t('model.providerList.saveFailedDescription'),
        type: 'error',
      })
    }
  }

  const handleDeleteProvider = async (id: string) => {
    if (confirm(t('model.providerList.deleteConfirm'))) {
      try {
        await deleteProvider(id)
        await loadProviders()
        onDeleteProvider(id)

        toast({
          title: t('model.providerList.deleteSuccessTitle'),
          description: t('model.providerList.deleteSuccessDescription'),
        })
      } catch (error) {
        console.error('Failed to delete provider:', error)
        toast({
          title: t('model.providerList.deleteFailedTitle'),
          description: t('model.providerList.deleteFailedDescription'),
          type: 'error',
        })
      }
    }
  }

  const handleEditProvider = (provider: ProviderConfig) => {
    openProviderFormDrawer(provider, t('model.providerList.editProvider'))
  }

  const handleHealthcheck = async (provider: ProviderConfig) => {
    try {
      await healthCheck(provider.id)
      toast({
        title: t('model.providerList.healthcheckSuccessTitle'),
        description: t('model.providerList.healthcheckSuccessDescription'),
      })
    } catch (error) {
      console.error('Healthcheck failed:', error)
      toast({
        title: t('model.providerList.healthcheckFailedTitle'),
        description: t('model.providerList.healthcheckFailedDescription'),
        type: 'error',
      })
    }
  }

  const handleSync = async (provider: ProviderConfig) => {
    try {
      await syncFromPlatform(provider.id)
      toast({
        title: t('model.providerList.syncSuccessTitle'),
        description: t('model.providerList.syncSuccessDescription'),
      })
    } catch (error) {
      console.error('Sync failed:', error)
      toast({
        title: t('model.providerList.syncFailedTitle'),
        description: t('model.providerList.syncFailedDescription'),
        type: 'error',
      })
    }
  }

  const handleViewJobs = async (provider: ProviderConfig) => {
    try {
      const jobs = await listSyncJobs(provider.id)
      toast({
        title: t('model.providerList.jobsTitle'),
        description: JSON.stringify(jobs.slice(0, 3)),
      })
    } catch (error) {
      console.error('Load jobs failed:', error)
      toast({
        title: t('model.providerList.jobsFailedTitle'),
        description: t('model.providerList.jobsFailedDescription'),
        type: 'error',
      })
    }
  }

  const handleAddProvider = () => {
    const newProvider: ProviderConfig = {
      id: '',
      adapterBackend: 'native',
      name: '',
      kind: ProviderKindEnum.OPENAI,
      status: 'active',
      baseUrl: '',
      credentialRef: '',
      syncPolicy: {
        auto_sync: false,
        interval_minutes: 360,
        recreate_deleted: false,
        default_enabled: true,
      },
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
    openProviderFormDrawer(newProvider, t('model.providerList.addProvider'))
  }

  const openProviderFormDrawer = (provider: ProviderConfig, title: string) => {
    drawer.open(
      <SettingSheet
        item={provider}
        index={0}
        onSave={handleSaveProvider}
        adapterBackends={adapterBackends}
        providerPresets={providerPresets}
      />,
      {
        direction: 'right',
        contentClassName: '!w-[600px] !max-w-[600px] h-full'
      }
    )
  }

  const supportBadgeVariant = (status: ProviderSupportStatus['support_status']) => {
    if (status === 'supported') return 'default'
    if (status === 'unavailable') return 'secondary'
    return 'outline'
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 overflow-y-hidden h-full">
        <DrawerHeader>
          <DrawerTitle className="text-sm font-bold">{resolvedTitle}</DrawerTitle>
          <DrawerDescription>
            {t('model.providerList.description')}
          </DrawerDescription>
        </DrawerHeader>
        <ScrollArea className="flex-1 h-full p-4">
          <div className="space-y-4 p-1">
            {supportMatrix.length > 0 && (
              <div className="grid gap-2">
                {supportMatrix.map((item) => (
                  <div key={item.provider_kind} className="rounded-md border p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-sm font-medium">{item.display_name}</div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          {t('model.providerList.support.capabilities', {
                            chat: item.chat_supported ? t('model.providerList.support.enabled') : t('model.providerList.support.disabled'),
                            embeddings: item.embeddings_supported ? t('model.providerList.support.enabled') : t('model.providerList.support.disabled'),
                            catalog: item.catalog_supported ? t('model.providerList.support.enabled') : t('model.providerList.support.disabled'),
                          })}
                        </div>
                      </div>
                      <Badge variant={supportBadgeVariant(item.support_status)}>
                        {t(`model.providerList.support.status.${item.support_status}`)}
                      </Badge>
                    </div>
                    <div className="mt-2 text-xs text-muted-foreground">
                      {t('model.providerList.support.configured', {
                        count: item.provider_count,
                      })}
                    </div>
                    {item.notes && (
                      <div className="mt-1 text-xs text-muted-foreground">{item.notes}</div>
                    )}
                  </div>
                ))}
              </div>
            )}
            {loading ? (
              <div className="text-center py-8 text-muted-foreground">
                {t('model.providerList.loading')}
              </div>
            ) : providers.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                {t('model.providerList.empty')}
              </div>
            ) : (
              providers.map((provider) => (
                <Card key={provider.id} className="cursor-pointer hover:bg-muted/50" onClick={() => handleEditProvider(provider)}>
                  <CardHeader className="p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle className="text-base">{provider.name}</CardTitle>
                        <CardDescription className="text-xs mt-1">{provider.kind} · {provider.adapterBackend}</CardDescription>
                      </div>
                      <Badge variant={provider.status === 'active' ? 'default' : 'secondary'}>
                        {provider.status === 'active' ? t('model.providerList.status.active') : t('model.providerList.status.inactive')}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="p-4 pt-0">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span>{t('model.providerList.fields.code')}: {provider.kind}</span>
                      <span>•</span>
                      <span>{t('model.providerList.fields.type')}: {provider.status}</span>
                    </div>
                    <div className="mt-3 flex items-center gap-2">
                      <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); handleHealthcheck(provider) }}>
                        <HeartPulse className="w-4 h-4 mr-1" />
                        {t('model.providerList.actions.healthcheck')}
                      </Button>
                      <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); handleSync(provider) }}>
                        <RefreshCw className="w-4 h-4 mr-1" />
                        {t('model.providerList.actions.sync')}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={(e) => { e.stopPropagation(); handleViewJobs(provider) }}>
                        <ListChecks className="w-4 h-4 mr-1" />
                        {t('model.providerList.actions.jobs')}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </ScrollArea>
      </div>

      <DrawerFooter className="border-t">
        <Button
          className="w-full"
          onClick={handleAddProvider}
        >
          <Plus className="w-4 h-4 mr-2" />
          {t('model.providerList.addProvider')}
        </Button>
      </DrawerFooter>
    </div>
  )
} 
