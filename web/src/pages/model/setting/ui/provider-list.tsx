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
} from '@/services/provider-service'
import { useToast } from '@/hooks/use-toast'
import { useTranslation } from '@/i18n'

// Provider kind enum
const ProviderKindEnum = {
  OPENAI: "openai",
  ANTHROPIC: "anthropic",
  GEMINI: "gemini",
  OPENAI_COMPAT: "openai_compat",
} as const

// Provider status enum
const ProviderStatusEnum = {
  active: "active",
  disabled: "disabled",
  error: "error"
} as const

export interface ProviderConfig {
  id: string
  name: string
  kind: typeof ProviderKindEnum[keyof typeof ProviderKindEnum]
  baseUrl?: string
  credentialRef?: string
  status: keyof typeof ProviderStatusEnum
  syncPolicy?: {
    auto_sync?: boolean
    interval_minutes?: number
    recreate_deleted?: boolean
    default_enabled?: boolean
  }
  createdAt?: string
  updatedAt?: string
}

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
  const [loading, setLoading] = useState(true)
  const resolvedTitle = title ?? t('system.model.providerList.title')

  // Load providers
  useEffect(() => {
    loadProviders()
  }, [])

  const loadProviders = async () => {
    try {
      setLoading(true)
      const data = await listProviders()
      setProviders(data)
    } catch (error) {
      console.error('Failed to load providers:', error)
      toast({
        title: t('system.model.providerList.loadFailedTitle'),
        description: t('system.model.providerList.loadFailedDescription'),
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
        title: t('system.model.providerList.saveSuccessTitle'),
        description: t('system.model.providerList.saveSuccessDescription'),
      })
    } catch (error) {
      console.error('Failed to save provider:', error)
      toast({
        title: t('system.model.providerList.saveFailedTitle'),
        description: t('system.model.providerList.saveFailedDescription'),
        type: 'error',
      })
    }
  }

  const handleDeleteProvider = async (id: string) => {
    if (confirm(t('system.model.providerList.deleteConfirm'))) {
      try {
        await deleteProvider(id)
        await loadProviders()
        onDeleteProvider(id)

        toast({
          title: t('system.model.providerList.deleteSuccessTitle'),
          description: t('system.model.providerList.deleteSuccessDescription'),
        })
      } catch (error) {
        console.error('Failed to delete provider:', error)
        toast({
          title: t('system.model.providerList.deleteFailedTitle'),
          description: t('system.model.providerList.deleteFailedDescription'),
          type: 'error',
        })
      }
    }
  }

  const handleEditProvider = (provider: ProviderConfig) => {
    openProviderFormDrawer(provider, t('system.model.providerList.editProvider'))
  }

  const handleHealthcheck = async (provider: ProviderConfig) => {
    try {
      await healthCheck(provider.id)
      toast({
        title: t('system.model.providerList.healthcheckSuccessTitle'),
        description: t('system.model.providerList.healthcheckSuccessDescription'),
      })
    } catch (error) {
      console.error('Healthcheck failed:', error)
      toast({
        title: t('system.model.providerList.healthcheckFailedTitle'),
        description: t('system.model.providerList.healthcheckFailedDescription'),
        type: 'error',
      })
    }
  }

  const handleSync = async (provider: ProviderConfig) => {
    try {
      await syncFromPlatform(provider.id)
      toast({
        title: t('system.model.providerList.syncSuccessTitle'),
        description: t('system.model.providerList.syncSuccessDescription'),
      })
    } catch (error) {
      console.error('Sync failed:', error)
      toast({
        title: t('system.model.providerList.syncFailedTitle'),
        description: t('system.model.providerList.syncFailedDescription'),
        type: 'error',
      })
    }
  }

  const handleViewJobs = async (provider: ProviderConfig) => {
    try {
      const jobs = await listSyncJobs(provider.id)
      toast({
        title: t('system.model.providerList.jobsTitle'),
        description: JSON.stringify(jobs.slice(0, 3)),
      })
    } catch (error) {
      console.error('Load jobs failed:', error)
      toast({
        title: t('system.model.providerList.jobsFailedTitle'),
        description: t('system.model.providerList.jobsFailedDescription'),
        type: 'error',
      })
    }
  }

  const handleAddProvider = () => {
    const newProvider: ProviderConfig = {
      id: '',
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
    openProviderFormDrawer(newProvider, t('system.model.providerList.addProvider'))
  }

  const openProviderFormDrawer = (provider: ProviderConfig, title: string) => {
    drawer.open(
      <SettingSheet
        item={provider}
        index={0}
        onSave={handleSaveProvider}
      />,
      {
        direction: 'right',
        contentClassName: '!w-[600px] !max-w-[600px] h-full'
      }
    )
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 overflow-y-hidden h-full">
        <DrawerHeader>
          <DrawerTitle className="text-sm font-bold">{resolvedTitle}</DrawerTitle>
          <DrawerDescription>
            {t('system.model.providerList.description')}
          </DrawerDescription>
        </DrawerHeader>
        <ScrollArea className="flex-1 h-full p-4">
          <div className="space-y-4 p-1">
            {loading ? (
              <div className="text-center py-8 text-muted-foreground">
                {t('system.model.providerList.loading')}
              </div>
            ) : providers.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                {t('system.model.providerList.empty')}
              </div>
            ) : (
              providers.map((provider) => (
                <Card key={provider.id} className="cursor-pointer hover:bg-muted/50" onClick={() => handleEditProvider(provider)}>
                  <CardHeader className="p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle className="text-base">{provider.name}</CardTitle>
                        <CardDescription className="text-xs mt-1">{provider.kind}</CardDescription>
                      </div>
                      <Badge variant={provider.status === 'active' ? 'default' : 'secondary'}>
                        {provider.status === 'active' ? t('system.model.providerList.status.active') : t('system.model.providerList.status.inactive')}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="p-4 pt-0">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span>{t('system.model.providerList.fields.code')}: {provider.kind}</span>
                      <span>•</span>
                      <span>{t('system.model.providerList.fields.type')}: {provider.status}</span>
                    </div>
                    <div className="mt-3 flex items-center gap-2">
                      <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); handleHealthcheck(provider) }}>
                        <HeartPulse className="w-4 h-4 mr-1" />
                        {t('system.model.providerList.actions.healthcheck')}
                      </Button>
                      <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); handleSync(provider) }}>
                        <RefreshCw className="w-4 h-4 mr-1" />
                        {t('system.model.providerList.actions.sync')}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={(e) => { e.stopPropagation(); handleViewJobs(provider) }}>
                        <ListChecks className="w-4 h-4 mr-1" />
                        {t('system.model.providerList.actions.jobs')}
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
          {t('system.model.providerList.addProvider')}
        </Button>
      </DrawerFooter>
    </div>
  )
} 
