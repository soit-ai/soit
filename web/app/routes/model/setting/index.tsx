import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { DrawerClose, DrawerDescription, DrawerFooter, DrawerHeader, DrawerTitle } from '@/components/ui/drawer'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useDrawer } from '@/hooks/use-drawer'
import { useToast } from '@/hooks/use-toast'
import { useTranslation } from '@/i18n'
import {
  getProviderSupportMatrix,
  type AdapterBackendSupport,
  type ProviderPreset,
} from '@/services/provider-service'
import type { ProviderConfig } from './ui/types'
import { useEffect, useState } from 'react'

const ProviderStatusOptions = [
  { label: 'active', value: 'active' },
  { label: 'disabled', value: 'disabled' },
  { label: 'error', value: 'error' },
] as const

const AuthTypeOptions = [
  { label: 'api_key', value: 'api_key' },
  { label: 'bearer', value: 'bearer' },
  { label: 'azure_ad', value: 'azure_ad' },
  { label: 'custom_header', value: 'custom_header' },
] as const

const BackoffOptions = [
  { label: 'exponential', value: 'exponential' },
  { label: 'linear', value: 'linear' },
  { label: 'none', value: 'none' },
] as const

const PricingSourceOptions = [
  { label: 'catalog', value: 'catalog' },
  { label: 'manual', value: 'manual' },
  { label: 'unknown', value: 'unknown' },
] as const

const RuntimeCapabilityKeys = ['chat', 'stream', 'embedding', 'image', 'audio', 'video', 'rerank'] as const
const DiagnosticsCapabilityKeys = ['healthcheck', 'chat', 'embedding'] as const

export type SettingSheetProps = {
  item?: ProviderConfig
  index: number
  onSave?: (data: ProviderConfig) => Promise<void> | void
  adapterBackends?: AdapterBackendSupport[]
  providerPresets?: ProviderPreset[]
}

const toNumber = (value: string) => {
  if (!value.trim()) return undefined
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : undefined
}

const formatList = (value?: string[]) => (value || []).join('\n')

const parseList = (value: string) => {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)
}

const formatNumberList = (value?: number[]) => (value || []).join(', ')

const parseNumberList = (value: string) => {
  return value
    .split(/[,\r\n]+/)
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isFinite(item))
}

const createInitialProvider = (item: ProviderConfig): ProviderConfig => ({
  id: item.id || '',
  adapterBackend: item.adapterBackend || 'native',
  slug: item.slug || item.kind || '',
  name: item.name || '',
  kind: item.kind || 'openai',
  baseUrl: item.baseUrl || '',
  credentialSecretId: item.credentialSecretId || '',
  status: item.status || 'active',
  lastSyncedAt: item.lastSyncedAt,
  lastHealthcheckAt: item.lastHealthcheckAt,
  lastHealthcheckError: item.lastHealthcheckError,
  syncPolicy: {
    catalog_supported: item.syncPolicy?.catalog_supported ?? true,
    auto_sync: item.syncPolicy?.auto_sync ?? false,
    interval_minutes: item.syncPolicy?.interval_minutes ?? 360,
    recreate_deleted: item.syncPolicy?.recreate_deleted ?? false,
    default_enabled: item.syncPolicy?.default_enabled ?? true,
    include_models: item.syncPolicy?.include_models || [],
    exclude_models: item.syncPolicy?.exclude_models || [],
  },
  connectionConfig: {
    api_version: item.connectionConfig?.api_version || '',
    timeout_ms: item.connectionConfig?.timeout_ms ?? 30000,
    retry_policy: {
      max_retries: item.connectionConfig?.retry_policy?.max_retries ?? 3,
      backoff: item.connectionConfig?.retry_policy?.backoff || 'exponential',
      retryable_status_codes: item.connectionConfig?.retry_policy?.retryable_status_codes || [],
    },
    rate_limit: {
      rpm: item.connectionConfig?.rate_limit?.rpm,
      tpm: item.connectionConfig?.rate_limit?.tpm,
      concurrency: item.connectionConfig?.rate_limit?.concurrency ?? 16,
    },
  },
  authConfig: {
    ...item.authConfig,
    auth_type: item.authConfig?.auth_type || 'bearer',
  },
  runtimeConfig: {
    ...item.runtimeConfig,
    litellm_provider: item.runtimeConfig?.litellm_provider,
    litellm_params: item.runtimeConfig?.litellm_params || {},
    diagnostics_supported: {
      healthcheck: item.runtimeConfig?.diagnostics_supported?.healthcheck ?? true,
      chat: item.runtimeConfig?.diagnostics_supported?.chat ?? true,
      embedding: item.runtimeConfig?.diagnostics_supported?.embedding ?? false,
    },
    runtime_support: {
      chat: item.runtimeConfig?.runtime_support?.chat ?? true,
      stream: item.runtimeConfig?.runtime_support?.stream ?? true,
      embedding: item.runtimeConfig?.runtime_support?.embedding ?? false,
      image: item.runtimeConfig?.runtime_support?.image ?? false,
      audio: item.runtimeConfig?.runtime_support?.audio ?? false,
      video: item.runtimeConfig?.runtime_support?.video ?? false,
      rerank: item.runtimeConfig?.runtime_support?.rerank ?? false,
    },
  },
  governanceConfig: {
    currency: item.governanceConfig?.currency || 'USD',
    pricing_source: item.governanceConfig?.pricing_source || 'unknown',
    egress_policy: {
      allow_external: item.governanceConfig?.egress_policy?.allow_external ?? true,
      allowed_domains: item.governanceConfig?.egress_policy?.allowed_domains || [],
    },
    data_policy: {
      files: item.governanceConfig?.data_policy?.files ?? false,
      images: item.governanceConfig?.data_policy?.images ?? false,
      audio: item.governanceConfig?.data_policy?.audio ?? false,
      video: item.governanceConfig?.data_policy?.video ?? false,
      sensitive_data: item.governanceConfig?.data_policy?.sensitive_data || 'deny',
    },
    log_level: item.governanceConfig?.log_level || 'summary',
    trace_enabled: item.governanceConfig?.trace_enabled ?? true,
  },
  source: item.source,
  templateId: item.templateId,
  pluginId: item.pluginId,
  pluginName: item.pluginName,
  pluginVersion: item.pluginVersion,
  metadata: item.metadata,
  createdAt: item.createdAt,
  updatedAt: item.updatedAt,
})

export function SettingSheet(props: SettingSheetProps) {
  const {
    item = {} as ProviderConfig,
    onSave,
    adapterBackends,
    providerPresets,
  } = props
  const { t } = useTranslation()
  const drawer = useDrawer()
  const { toast } = useToast()
  const [formData, setFormData] = useState<ProviderConfig>(() => createInitialProvider(item))
  const [runtimeAdapterBackends, setRuntimeAdapterBackends] = useState(
    adapterBackends || [],
  )
  const [runtimeProviderPresets, setRuntimeProviderPresets] = useState(
    providerPresets || [],
  )

  useEffect(() => {
    if (adapterBackends || providerPresets) {
      setRuntimeAdapterBackends(adapterBackends || [])
      setRuntimeProviderPresets(providerPresets || [])
      return
    }
    let active = true
    getProviderSupportMatrix()
      .then((support) => {
        if (!active) return
        setRuntimeAdapterBackends(support.adapterBackends)
        setRuntimeProviderPresets(support.providerPresets)
      })
      .catch(() => undefined)
    return () => {
      active = false
    }
  }, [adapterBackends, providerPresets])

  const selectedAdapterSupport = runtimeAdapterBackends.find(
    (item) => item.adapter_backend === formData.adapterBackend,
  )
  const selectedProviderPreset = runtimeProviderPresets.find(
    (item) => item.provider_kind === formData.kind,
  )
  const visibleProviderPresets = runtimeProviderPresets.length
    ? runtimeProviderPresets
    : [{ provider_kind: formData.kind, display_name: formData.kind }]
  const visibleAdapterBackends = runtimeAdapterBackends.length
    ? runtimeAdapterBackends
    : [
        { adapter_backend: 'native' as const, display_name: 'Native', available: true },
        { adapter_backend: 'litellm' as const, display_name: 'LiteLLM SDK', available: true },
      ]

  const handleInputChange = <K extends keyof ProviderConfig>(field: K, value: ProviderConfig[K]) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }))
  }

  const handleProviderKindChange = (kind: string) => {
    const preset = runtimeProviderPresets.find((item) => item.provider_kind === kind)
    setFormData((previous) => ({
      ...previous,
      kind,
      slug: previous.id ? previous.slug : kind,
      adapterBackend: preset?.default_adapter_backend || previous.adapterBackend,
      runtimeConfig: {
        ...previous.runtimeConfig,
        litellm_provider: preset?.litellm_provider,
      },
    }))
  }

  const handleSyncPolicyChange = (field: string, value: unknown) => {
    setFormData((prev) => ({
      ...prev,
      syncPolicy: {
        ...prev.syncPolicy,
        [field]: value,
      },
    }))
  }

  const handleConnectionConfigChange = (field: string, value: unknown) => {
    setFormData((prev) => ({
      ...prev,
      connectionConfig: {
        ...prev.connectionConfig,
        [field]: value,
      },
    }))
  }

  const handleRetryPolicyChange = (field: string, value: unknown) => {
    setFormData((prev) => ({
      ...prev,
      connectionConfig: {
        ...prev.connectionConfig,
        retry_policy: {
          ...prev.connectionConfig?.retry_policy,
          [field]: value,
        },
      },
    }))
  }

  const handleRateLimitChange = (field: string, value: unknown) => {
    setFormData((prev) => ({
      ...prev,
      connectionConfig: {
        ...prev.connectionConfig,
        rate_limit: {
          ...prev.connectionConfig?.rate_limit,
          [field]: value,
        },
      },
    }))
  }

  const handleAuthConfigChange = (field: string, value: unknown) => {
    setFormData((prev) => ({
      ...prev,
      authConfig: {
        ...prev.authConfig,
        [field]: value,
      },
    }))
  }

  const handleDiagnosticsChange = (field: string, value: boolean) => {
    setFormData((prev) => ({
      ...prev,
      runtimeConfig: {
        ...prev.runtimeConfig,
        diagnostics_supported: {
          ...prev.runtimeConfig?.diagnostics_supported,
          [field]: value,
        },
      },
    }))
  }

  const handleRuntimeSupportChange = (field: string, value: boolean) => {
    setFormData((prev) => ({
      ...prev,
      runtimeConfig: {
        ...prev.runtimeConfig,
        runtime_support: {
          ...prev.runtimeConfig?.runtime_support,
          [field]: value,
        },
      },
    }))
  }

  const handleGovernanceConfigChange = (field: string, value: unknown) => {
    setFormData((prev) => ({
      ...prev,
      governanceConfig: {
        ...prev.governanceConfig,
        [field]: value,
      },
    }))
  }

  const handleEgressPolicyChange = (field: string, value: unknown) => {
    setFormData((prev) => ({
      ...prev,
      governanceConfig: {
        ...prev.governanceConfig,
        egress_policy: {
          ...prev.governanceConfig?.egress_policy,
          [field]: value,
        },
      },
    }))
  }

  const handleDataPolicyChange = (field: string, value: unknown) => {
    setFormData((prev) => ({
      ...prev,
      governanceConfig: {
        ...prev.governanceConfig,
        data_policy: {
          ...prev.governanceConfig?.data_policy,
          [field]: value,
        },
      },
    }))
  }

  const handleSave = async () => {
    try {
      await onSave?.(formData)
      toast({
        title: t('model.providerSettings.actions.saveSuccessTitle'),
        description: t('model.providerSettings.actions.saveSuccessDescription'),
      })
      drawer.close()
    } catch (error) {
      console.error('Failed to save provider:', error)
      toast({
        title: t('model.providerSettings.actions.saveFailedTitle'),
        description: t('model.providerSettings.actions.saveFailedDescription'),
        type: 'error',
      })
    }
  }

  const credentialStatus = formData.credentialSecretId
    ? formData.lastHealthcheckError
      ? t('model.providerSettings.status.credentialError')
      : t('model.providerSettings.status.credentialConfigured')
    : t('model.providerSettings.status.credentialMissing')
  const catalogStatus = formData.syncPolicy?.catalog_supported
    ? t('model.providerSettings.status.supported')
    : t('model.providerSettings.status.disabled')
  const renderSupportStatus = (value?: boolean) => {
    if (value === undefined) return t('model.providerSettings.status.unknown')
    return value ? t('model.providerSettings.status.supported') : t('model.providerSettings.status.unsupported')
  }
  const getMergedSupport = (key: (typeof RuntimeCapabilityKeys)[number]) => {
    const runtimeSupported = formData.runtimeConfig?.runtime_support?.[key]
    const diagnosticsSupported = formData.runtimeConfig?.diagnostics_supported?.[key]
    if (runtimeSupported === undefined) return undefined
    return Boolean(runtimeSupported) && diagnosticsSupported !== false
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto">
        <DrawerHeader>
          <DrawerTitle className="text-sm font-bold">{t('model.providerSettings.title')}</DrawerTitle>
          <DrawerDescription>{t('model.providerSettings.description')}</DrawerDescription>
        </DrawerHeader>

        <div className="p-4">
          <Tabs defaultValue="basic" className="w-full">
            <TabsList className="mb-6 grid w-full grid-cols-5">
              <TabsTrigger value="basic">{t('model.providerSettings.tabs.basic')}</TabsTrigger>
              <TabsTrigger value="connection">{t('model.providerSettings.tabs.connectionAuth')}</TabsTrigger>
              <TabsTrigger value="catalog">{t('model.providerSettings.tabs.catalogSync')}</TabsTrigger>
              <TabsTrigger value="runtime">{t('model.providerSettings.tabs.diagnosticsRuntime')}</TabsTrigger>
              <TabsTrigger value="governance">{t('model.providerSettings.tabs.securityObservability')}</TabsTrigger>
            </TabsList>

            <TabsContent value="basic" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>{t('model.providerSettings.sections.basicInfo.title')}</CardTitle>
                  <CardDescription>{t('model.providerSettings.sections.basicInfo.description')}</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="provider-id">{t('model.providerSettings.fields.providerId')}</Label>
                    <Input id="provider-id" value={formData.id || ''} readOnly />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="provider-slug">{t('model.providerSettings.fields.slug')}</Label>
                    <Input
                      id="provider-slug"
                      value={formData.slug || ''}
                      onChange={(event) => handleInputChange('slug', event.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="provider-name">{t('model.providerSettings.fields.name')}</Label>
                    <Input
                      id="provider-name"
                      placeholder={t('model.providerSettings.fields.namePlaceholder')}
                      value={formData.name}
                      onChange={(event) => handleInputChange('name', event.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>{t('model.providerSettings.fields.kind')}</Label>
                    <Select value={formData.kind} onValueChange={handleProviderKindChange}>
                      <SelectTrigger>
                        <SelectValue placeholder={t('model.providerSettings.fields.kindPlaceholder')} />
                      </SelectTrigger>
                      <SelectContent>
                        {visibleProviderPresets.map((preset) => (
                          <SelectItem key={preset.provider_kind} value={preset.provider_kind}>
                            {preset.display_name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>{t('model.providerSettings.fields.status')}</Label>
                    <Select value={formData.status} onValueChange={(value) => handleInputChange('status', value as ProviderConfig['status'])}>
                      <SelectTrigger>
                        <SelectValue placeholder={t('model.providerSettings.fields.statusPlaceholder')} />
                      </SelectTrigger>
                      <SelectContent>
                        {ProviderStatusOptions.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>{t('model.providerSettings.fields.adapterBackend')}</Label>
                    <Select
                      value={formData.adapterBackend}
                      onValueChange={(value) => handleInputChange('adapterBackend', value as ProviderConfig['adapterBackend'])}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {visibleAdapterBackends.map((option) => (
                          <SelectItem
                            key={option.adapter_backend}
                            value={option.adapter_backend}
                            disabled={runtimeAdapterBackends.some(
                              (item) => item.adapter_backend === option.adapter_backend && !item.available,
                            ) || Boolean(
                              selectedProviderPreset
                              && !selectedProviderPreset.supported_adapter_backends.includes(option.adapter_backend),
                            )}
                          >
                            {option.display_name}
                            {runtimeAdapterBackends.some(
                              (item) => item.adapter_backend === option.adapter_backend && !item.available,
                            )
                              ? ` (${t('model.providerSettings.status.unavailable')})`
                              : ''}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      {selectedAdapterSupport?.available === false
                        ? t('model.providerSettings.hints.adapterUnavailable', {
                            installHint: selectedAdapterSupport.install_hint,
                          })
                        : t('model.providerSettings.hints.adapterBackend')}
                    </p>
                  </div>
                  <div className="space-y-2 md:col-span-2">
                    <Label>{t('model.providerSettings.fields.boundary')}</Label>
                    <p className="rounded-lg border bg-muted/30 p-3 text-sm text-muted-foreground">
                      {t('model.providerSettings.hints.providerBoundary')}
                    </p>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="connection" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>{t('model.providerSettings.sections.connection.title')}</CardTitle>
                  <CardDescription>{t('model.providerSettings.sections.connection.description')}</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2 md:col-span-2">
                    <Label htmlFor="provider-base-url">{t('model.providerSettings.fields.baseUrl')}</Label>
                    <Input
                      id="provider-base-url"
                      placeholder="https://api.example.com/v1"
                      value={formData.baseUrl || ''}
                      onChange={(event) => handleInputChange('baseUrl', event.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="provider-api-version">{t('model.providerSettings.fields.apiVersion')}</Label>
                    <Input
                      id="provider-api-version"
                      value={formData.connectionConfig?.api_version || ''}
                      onChange={(event) => handleConnectionConfigChange('api_version', event.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="provider-timeout-ms">{t('model.providerSettings.fields.timeoutMs')}</Label>
                    <Input
                      id="provider-timeout-ms"
                      type="number"
                      value={formData.connectionConfig?.timeout_ms ?? ''}
                      onChange={(event) => handleConnectionConfigChange('timeout_ms', toNumber(event.target.value))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="provider-max-retries">{t('model.providerSettings.fields.maxRetries')}</Label>
                    <Input
                      id="provider-max-retries"
                      type="number"
                      value={formData.connectionConfig?.retry_policy?.max_retries ?? ''}
                      onChange={(event) => handleRetryPolicyChange('max_retries', toNumber(event.target.value))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>{t('model.providerSettings.fields.backoff')}</Label>
                    <Select
                      value={formData.connectionConfig?.retry_policy?.backoff || 'exponential'}
                      onValueChange={(value) => handleRetryPolicyChange('backoff', value)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {BackoffOptions.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2 md:col-span-2">
                    <Label htmlFor="provider-retryable-status-codes">{t('model.providerSettings.fields.retryableStatusCodes')}</Label>
                    <Input
                      id="provider-retryable-status-codes"
                      placeholder="429, 500, 502, 503, 504"
                      value={formatNumberList(formData.connectionConfig?.retry_policy?.retryable_status_codes)}
                      onChange={(event) => handleRetryPolicyChange('retryable_status_codes', parseNumberList(event.target.value))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="provider-rpm">{t('model.providerSettings.fields.rpm')}</Label>
                    <Input
                      id="provider-rpm"
                      type="number"
                      value={formData.connectionConfig?.rate_limit?.rpm ?? ''}
                      onChange={(event) => handleRateLimitChange('rpm', toNumber(event.target.value))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="provider-tpm">{t('model.providerSettings.fields.tpm')}</Label>
                    <Input
                      id="provider-tpm"
                      type="number"
                      value={formData.connectionConfig?.rate_limit?.tpm ?? ''}
                      onChange={(event) => handleRateLimitChange('tpm', toNumber(event.target.value))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="provider-concurrency">{t('model.providerSettings.fields.concurrency')}</Label>
                    <Input
                      id="provider-concurrency"
                      type="number"
                      value={formData.connectionConfig?.rate_limit?.concurrency ?? ''}
                      onChange={(event) => handleRateLimitChange('concurrency', toNumber(event.target.value))}
                    />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>{t('model.providerSettings.sections.auth.title')}</CardTitle>
                  <CardDescription>{t('model.providerSettings.sections.auth.description')}</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label>{t('model.providerSettings.fields.authType')}</Label>
                    <Select
                      value={formData.authConfig?.auth_type || 'bearer'}
                      onValueChange={(value) => handleAuthConfigChange('auth_type', value)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {AuthTypeOptions.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>{t('model.providerSettings.fields.credentialStatus')}</Label>
                    <Input value={credentialStatus} readOnly />
                  </div>
                  <div className="space-y-2 md:col-span-2">
                    <Label htmlFor="provider-credential-secret-id">{t('model.providerSettings.fields.credentialSecretId')}</Label>
                    <Input
                      id="provider-credential-secret-id"
                      value={formData.credentialSecretId || ''}
                      onChange={(event) => handleInputChange('credentialSecretId', event.target.value)}
                    />
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="catalog" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>{t('model.providerSettings.sections.catalog.title')}</CardTitle>
                  <CardDescription>{t('model.providerSettings.sections.catalog.description')}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="flex items-center justify-between rounded-lg border p-3">
                      <div>
                        <Label htmlFor="catalog-supported">{t('model.providerSettings.fields.catalogSupported')}</Label>
                        <p className="text-xs text-muted-foreground">{t('model.providerSettings.hints.catalogSupported')}</p>
                      </div>
                      <Switch
                        id="catalog-supported"
                        checked={formData.syncPolicy?.catalog_supported ?? true}
                        onCheckedChange={(checked) => handleSyncPolicyChange('catalog_supported', checked)}
                      />
                    </div>
                    <div className="flex items-center justify-between rounded-lg border p-3">
                      <div>
                        <Label htmlFor="auto-sync">{t('model.providerSettings.fields.autoSync')}</Label>
                        <p className="text-xs text-muted-foreground">{t('model.providerSettings.hints.autoSync')}</p>
                      </div>
                      <Switch
                        id="auto-sync"
                        checked={formData.syncPolicy?.auto_sync ?? false}
                        onCheckedChange={(checked) => handleSyncPolicyChange('auto_sync', checked)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="sync-interval">{t('model.providerSettings.fields.syncInterval')}</Label>
                      <Input
                        id="sync-interval"
                        type="number"
                        value={formData.syncPolicy?.interval_minutes ?? ''}
                        onChange={(event) => handleSyncPolicyChange('interval_minutes', toNumber(event.target.value))}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="last-synced-at">{t('model.providerSettings.fields.lastSyncedAt')}</Label>
                      <Input id="last-synced-at" value={formData.lastSyncedAt || '--'} readOnly />
                    </div>
                    <div className="flex items-center justify-between rounded-lg border p-3">
                      <div>
                        <Label htmlFor="default-enabled">{t('model.providerSettings.fields.defaultEnabled')}</Label>
                        <p className="text-xs text-muted-foreground">{t('model.providerSettings.hints.defaultEnabled')}</p>
                      </div>
                      <Switch
                        id="default-enabled"
                        checked={formData.syncPolicy?.default_enabled ?? true}
                        onCheckedChange={(checked) => handleSyncPolicyChange('default_enabled', checked)}
                      />
                    </div>
                    <div className="flex items-center justify-between rounded-lg border p-3">
                      <div>
                        <Label htmlFor="recreate-deleted">{t('model.providerSettings.fields.recreateDeleted')}</Label>
                        <p className="text-xs text-muted-foreground">{t('model.providerSettings.hints.recreateDeleted')}</p>
                      </div>
                      <Switch
                        id="recreate-deleted"
                        checked={formData.syncPolicy?.recreate_deleted ?? false}
                        onCheckedChange={(checked) => handleSyncPolicyChange('recreate_deleted', checked)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="include-models">{t('model.providerSettings.fields.includeModels')}</Label>
                      <textarea
                        id="include-models"
                        className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm"
                        value={formatList(formData.syncPolicy?.include_models)}
                        onChange={(event) => handleSyncPolicyChange('include_models', parseList(event.target.value))}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="exclude-models">{t('model.providerSettings.fields.excludeModels')}</Label>
                      <textarea
                        id="exclude-models"
                        className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm"
                        value={formatList(formData.syncPolicy?.exclude_models)}
                        onChange={(event) => handleSyncPolicyChange('exclude_models', parseList(event.target.value))}
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="runtime" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>{t('model.providerSettings.sections.diagnostics.title')}</CardTitle>
                  <CardDescription>{t('model.providerSettings.sections.diagnostics.description')}</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-3">
                  {DiagnosticsCapabilityKeys.map((key) => (
                    <div key={key} className="flex items-center justify-between rounded-lg border p-3">
                      <Label htmlFor={`diagnostics-${key}`}>{t(`model.providerSettings.runtime.${key}`)}</Label>
                      <Switch
                        id={`diagnostics-${key}`}
                        checked={formData.runtimeConfig?.diagnostics_supported?.[key] ?? false}
                        onCheckedChange={(checked) => handleDiagnosticsChange(key, checked)}
                      />
                    </div>
                  ))}
                  <div className="space-y-2 md:col-span-3">
                    <Label htmlFor="last-healthcheck-at">{t('model.providerSettings.fields.lastHealthcheckAt')}</Label>
                    <Input id="last-healthcheck-at" value={formData.lastHealthcheckAt || '--'} readOnly />
                  </div>
                  <div className="space-y-2 md:col-span-3">
                    <Label htmlFor="last-healthcheck-error">{t('model.providerSettings.fields.lastHealthcheckError')}</Label>
                    <Input id="last-healthcheck-error" value={formData.lastHealthcheckError || '--'} readOnly />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>{t('model.providerSettings.sections.runtime.title')}</CardTitle>
                  <CardDescription>{t('model.providerSettings.sections.runtime.description')}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <p className="rounded-lg border bg-muted/30 p-3 text-sm text-muted-foreground">
                    {t('model.providerSettings.hints.runtimeMerge')}
                  </p>
                  <div className="grid gap-3 md:grid-cols-2">
                    {RuntimeCapabilityKeys.map((key) => (
                      <div key={key} className="flex items-center justify-between rounded-lg border p-3">
                        <div>
                          <Label htmlFor={`runtime-${key}`}>{t(`model.providerSettings.runtime.${key}`)}</Label>
                          <p className="text-xs text-muted-foreground">{t('model.providerSettings.hints.runtimeSource')}</p>
                        </div>
                        <Switch
                          id={`runtime-${key}`}
                          checked={formData.runtimeConfig?.runtime_support?.[key] ?? false}
                          onCheckedChange={(checked) => handleRuntimeSupportChange(key, checked)}
                        />
                      </div>
                    ))}
                  </div>
                  <div className="overflow-hidden rounded-lg border">
                    <div className="border-b bg-muted/30 px-3 py-2 text-sm font-medium">
                      {t('model.providerSettings.fields.capabilityMatrix')}
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead className="bg-muted/20 text-muted-foreground">
                          <tr>
                            <th className="px-3 py-2 text-left font-medium">{t('model.providerSettings.fields.capability')}</th>
                            <th className="px-3 py-2 text-left font-medium">{t('model.providerSettings.fields.catalog')}</th>
                            <th className="px-3 py-2 text-left font-medium">{t('model.providerSettings.fields.diagnostics')}</th>
                            <th className="px-3 py-2 text-left font-medium">{t('model.providerSettings.fields.runtimeResult')}</th>
                            <th className="px-3 py-2 text-left font-medium">{t('model.providerSettings.fields.mergedResult')}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {RuntimeCapabilityKeys.map((key) => (
                            <tr key={key} className="border-t">
                              <td className="px-3 py-2 font-medium">{t(`model.providerSettings.runtime.${key}`)}</td>
                              <td className="px-3 py-2 text-muted-foreground">{catalogStatus}</td>
                              <td className="px-3 py-2 text-muted-foreground">
                                {renderSupportStatus(formData.runtimeConfig?.diagnostics_supported?.[key])}
                              </td>
                              <td className="px-3 py-2 text-muted-foreground">
                                {renderSupportStatus(formData.runtimeConfig?.runtime_support?.[key])}
                              </td>
                              <td className="px-3 py-2 text-muted-foreground">{renderSupportStatus(getMergedSupport(key))}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="governance" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>{t('model.providerSettings.sections.security.title')}</CardTitle>
                  <CardDescription>{t('model.providerSettings.sections.security.description')}</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-4 md:grid-cols-2">
                  <div className="flex items-center justify-between rounded-lg border p-3">
                    <div>
                      <Label htmlFor="allow-external">{t('model.providerSettings.fields.allowExternal')}</Label>
                      <p className="text-xs text-muted-foreground">{t('model.providerSettings.hints.allowExternal')}</p>
                    </div>
                    <Switch
                      id="allow-external"
                      checked={formData.governanceConfig?.egress_policy?.allow_external ?? true}
                      onCheckedChange={(checked) => handleEgressPolicyChange('allow_external', checked)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="allowed-domains">{t('model.providerSettings.fields.allowedDomains')}</Label>
                    <textarea
                      id="allowed-domains"
                      className="min-h-20 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm"
                      value={formatList(formData.governanceConfig?.egress_policy?.allowed_domains)}
                      onChange={(event) => handleEgressPolicyChange('allowed_domains', parseList(event.target.value))}
                    />
                  </div>
                  {(['files', 'images', 'audio', 'video'] as const).map((key) => (
                    <div key={key} className="flex items-center justify-between rounded-lg border p-3">
                      <Label htmlFor={`data-policy-${key}`}>{t(`model.providerSettings.dataPolicy.${key}`)}</Label>
                      <Switch
                        id={`data-policy-${key}`}
                        checked={formData.governanceConfig?.data_policy?.[key] ?? false}
                        onCheckedChange={(checked) => handleDataPolicyChange(key, checked)}
                      />
                    </div>
                  ))}
                  <div className="space-y-2 md:col-span-2">
                    <Label htmlFor="sensitive-data">{t('model.providerSettings.fields.sensitiveData')}</Label>
                    <Input
                      id="sensitive-data"
                      value={formData.governanceConfig?.data_policy?.sensitive_data || ''}
                      onChange={(event) => handleDataPolicyChange('sensitive_data', event.target.value)}
                    />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>{t('model.providerSettings.sections.observability.title')}</CardTitle>
                  <CardDescription>{t('model.providerSettings.sections.observability.description')}</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="currency">{t('model.providerSettings.fields.currency')}</Label>
                    <Input
                      id="currency"
                      value={formData.governanceConfig?.currency || ''}
                      onChange={(event) => handleGovernanceConfigChange('currency', event.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>{t('model.providerSettings.fields.pricingSource')}</Label>
                    <Select
                      value={formData.governanceConfig?.pricing_source || 'unknown'}
                      onValueChange={(value) => handleGovernanceConfigChange('pricing_source', value)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {PricingSourceOptions.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="log-level">{t('model.providerSettings.fields.logLevel')}</Label>
                    <Input
                      id="log-level"
                      value={formData.governanceConfig?.log_level || ''}
                      onChange={(event) => handleGovernanceConfigChange('log_level', event.target.value)}
                    />
                  </div>
                  <div className="flex items-center justify-between rounded-lg border p-3">
                    <div>
                      <Label htmlFor="trace-enabled">{t('model.providerSettings.fields.traceEnabled')}</Label>
                      <p className="text-xs text-muted-foreground">{t('model.providerSettings.hints.traceEnabled')}</p>
                    </div>
                    <Switch
                      id="trace-enabled"
                      checked={formData.governanceConfig?.trace_enabled ?? true}
                      onCheckedChange={(checked) => handleGovernanceConfigChange('trace_enabled', checked)}
                    />
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </div>

      <DrawerFooter className="border-t flex-col gap-4">
        <div className="flex w-full justify-between gap-4">
          <DrawerClose asChild className="flex-1">
            <Button variant="outline">{t('common.operation.cancel')}</Button>
          </DrawerClose>
          <Button className="flex-1" onClick={handleSave}>
            {t('model.providerSettings.actions.saveChanges')}
          </Button>
        </div>
      </DrawerFooter>
    </div>
  )
}

export default SettingSheet
