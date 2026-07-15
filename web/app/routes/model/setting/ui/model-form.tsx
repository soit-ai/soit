import { useMemo, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { DrawerClose, DrawerDescription, DrawerFooter, DrawerHeader, DrawerTitle } from '@/components/ui/drawer'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { useTranslation } from '@/i18n'

import type {
  ModelArchitectureConfig,
  ModelCapabilityMatrixEntry,
  ModelCapabilityMatrixConfig,
  ModelConfig,
  ModelDiagnosticsConfig,
  ModelFormProps,
  ModelParameterConfig,
  ModelPricingConfig,
} from './types'

const CAPABILITY_KEYS = [
  'chat',
  'streaming',
  'embedding',
  'vision',
  'file_input',
  'audio_input',
  'video_input',
  'image_output',
  'tool_calling',
  'structured_outputs',
  'reasoning',
  'rerank',
] as const

const PARAMETER_KEYS = [
  'temperature',
  'top_p',
  'max_tokens',
  'tools',
  'response_format',
  'reasoning',
  'seed',
  'presence_penalty',
  'frequency_penalty',
  'stop',
  'metadata',
] as const

function numberValue(value: string) {
  if (value.trim() === '') return undefined
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : undefined
}

function splitLines(value?: string[]) {
  return (value || []).join('\n')
}

function lines(value: string) {
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean)
}

function unique(values: string[]) {
  return Array.from(new Set(values))
}

function defaultArchitecture(model: ModelConfig): ModelArchitectureConfig {
  return {
    modality: model.architecture?.modality || 'text->text',
    input_modalities: model.architecture?.input_modalities || ['text'],
    output_modalities: model.architecture?.output_modalities || ['text'],
    tokenizer: model.architecture?.tokenizer || 'GPT',
  }
}

function defaultCapabilityMatrix(model: ModelConfig): ModelCapabilityMatrixConfig {
  const matrix = { ...(model.capabilityMatrix || {}) }
  CAPABILITY_KEYS.forEach((key) => {
    matrix[key] = {
      catalog: matrix[key]?.catalog ?? null,
      diagnostics: matrix[key]?.diagnostics ?? null,
      runtime: matrix[key]?.runtime ?? null,
      merged: matrix[key]?.merged ?? null,
      user_override: matrix[key]?.user_override || 'auto',
    }
  })
  return matrix
}

function mergedCapability(entry: ModelCapabilityMatrixEntry): boolean | null {
  if (entry.user_override === 'force_on') return true
  if (entry.user_override === 'force_off') return false
  if (entry.user_override === 'enable_after_diagnostics') return entry.diagnostics === true
  return entry.diagnostics ?? entry.runtime ?? entry.catalog ?? entry.merged ?? null
}

function defaultParameterConfig(model: ModelConfig): ModelParameterConfig {
  return {
    max_input_files: model.parameterConfig?.max_input_files ?? 0,
    max_image_count: model.parameterConfig?.max_image_count ?? 0,
    max_audio_seconds: model.parameterConfig?.max_audio_seconds ?? 0,
    max_video_seconds: model.parameterConfig?.max_video_seconds ?? 0,
    supported_parameters: model.parameterConfig?.supported_parameters || ['temperature', 'top_p', 'max_tokens'],
    default_parameters: {
      temperature: 0.7,
      top_p: 1,
      max_tokens: 4096,
      ...(model.parameterConfig?.default_parameters || {}),
    },
  }
}

function defaultPricing(model: ModelConfig): ModelPricingConfig {
  return {
    currency: model.pricing?.currency || 'USD',
    pricing_source: model.pricing?.pricing_source || 'manual',
    prompt: { amount: 0, unit: '1M_tokens', ...(model.pricing?.prompt || {}) },
    completion: { amount: 0, unit: '1M_tokens', ...(model.pricing?.completion || {}) },
    image: { amount: 0, unit: 'image', enabled: false, ...(model.pricing?.image || {}) },
    request: { amount: 0, unit: 'request', ...(model.pricing?.request || {}) },
    override_policy: model.pricing?.override_policy || { preserve_user_overrides: true },
    estimate: model.pricing?.estimate || { input_tokens: 12000, output_tokens: 2000, requests: 1 },
  }
}

function defaultDiagnostics(model: ModelConfig): ModelDiagnosticsConfig {
  return {
    last_test_status: model.diagnostics?.last_test_status || 'skipped',
    last_test_at: model.diagnostics?.last_test_at || '',
    last_test_error: model.diagnostics?.last_test_error || '',
    test_mode: model.diagnostics?.test_mode || 'chat',
    test_prompt: model.diagnostics?.test_prompt || 'Please reply with one sentence: diagnostics passed.',
    timeout_ms: model.diagnostics?.timeout_ms ?? 30000,
    support: {
      catalog: 'unknown',
      diagnostics: 'unknown',
      runtime: 'unknown',
      ...(model.diagnostics?.support || {}),
    },
    runtime_stats: {
      month_calls: 0,
      month_tokens: 0,
      avg_latency_ms: 0,
      error_rate: 0,
      ...(model.diagnostics?.runtime_stats || {}),
    },
    override_reason: model.diagnostics?.override_reason || '',
  }
}

function normalizeModel(model: ModelConfig): ModelConfig {
  return {
    ...model,
    architecture: defaultArchitecture(model),
    capabilityMatrix: defaultCapabilityMatrix(model),
    parameterConfig: defaultParameterConfig(model),
    pricing: defaultPricing(model),
    diagnostics: defaultDiagnostics(model),
    rawMeta: model.rawMeta || {},
  }
}

export function ModelForm({ model, onSave, onCancel, onChange, title }: ModelFormProps) {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState('basic')
  const [formData, setFormData] = useState<ModelConfig>(() => normalizeModel(model))
  const [rawMetaText, setRawMetaText] = useState(() => JSON.stringify(model.rawMeta || {}, null, 2))
  const [userOverridesText, setUserOverridesText] = useState(() => JSON.stringify(model.userOverridesJson || {}, null, 2))
  const resolvedTitle = title ?? t('model.form.title')
  const modelRef = useMemo(() => `${formData.providerId || 'provider'}/${formData.modelId || 'model'}`, [formData.modelId, formData.providerId])

  const updateForm = (updater: (current: ModelConfig) => ModelConfig) => {
    const next = updater(formData)
    setFormData(next)
    onChange(next)
  }

  const updateField = <K extends keyof ModelConfig>(field: K, value: ModelConfig[K]) => {
    updateForm((current) => ({ ...current, [field]: value }))
  }

  const updateArchitecture = (patch: Partial<ModelArchitectureConfig>) => {
    updateForm((current) => ({ ...current, architecture: { ...(current.architecture || {}), ...patch } }))
  }

  const updateCapability = (key: string, patch: Record<string, any>) => {
    updateForm((current) => {
      const entry = {
        ...(current.capabilityMatrix?.[key] || {}),
        ...patch,
      }
      const merged = mergedCapability(entry)
      return {
        ...current,
        capabilityMatrix: {
          ...(current.capabilityMatrix || {}),
          [key]: { ...entry, merged },
        },
        capabilities: merged
          ? unique([...(current.capabilities || []), key])
          : (current.capabilities || []).filter((item) => item !== key),
      }
    })
  }

  const formatCapabilitySupport = (value: boolean | null | undefined) => {
    if (value === true) return 'supported'
    if (value === false) return 'unsupported'
    return 'unknown'
  }

  const updateParameterConfig = (patch: Partial<ModelParameterConfig>) => {
    updateForm((current) => ({ ...current, parameterConfig: { ...(current.parameterConfig || {}), ...patch } }))
  }

  const updateDefaultParameter = (key: string, value: any) => {
    updateForm((current) => ({
      ...current,
      parameterConfig: {
        ...(current.parameterConfig || {}),
        default_parameters: {
          ...(current.parameterConfig?.default_parameters || {}),
          [key]: value,
        },
      },
    }))
  }

  const updatePricing = (patch: Partial<ModelPricingConfig>) => {
    updateForm((current) => ({ ...current, pricing: { ...(current.pricing || {}), ...patch } }))
  }

  const updatePricingBucket = (bucket: 'prompt' | 'completion' | 'image' | 'request', patch: Record<string, any>) => {
    updatePricing({ [bucket]: { ...(formData.pricing?.[bucket] || {}), ...patch } })
  }

  const updateDiagnostics = (patch: Partial<ModelDiagnosticsConfig>) => {
    updateForm((current) => ({ ...current, diagnostics: { ...(current.diagnostics || {}), ...patch } }))
  }

  const updateDiagnosticsObject = (bucket: 'support' | 'runtime_stats', patch: Record<string, any>) => {
    updateDiagnostics({ [bucket]: { ...(formData.diagnostics?.[bucket] || {}), ...patch } })
  }

  const updateRawMeta = (value: string) => {
    setRawMetaText(value)
    try {
      updateField('rawMeta', JSON.parse(value))
    } catch {
      // Keep editing text; only valid JSON is written to the model payload.
    }
  }

  const updateUserOverrides = (value: string) => {
    setUserOverridesText(value)
    try {
      updateField('userOverridesJson', JSON.parse(value))
    } catch {
      // Keep editing text; only valid JSON is written to the model payload.
    }
  }

  return (
    <form className="flex h-full flex-col">
      <DrawerHeader>
        <DrawerTitle className="text-sm font-bold">{resolvedTitle}</DrawerTitle>
        <DrawerDescription>{t('model.form.description')}</DrawerDescription>
      </DrawerHeader>

      <div className="flex-1 overflow-y-auto p-4">
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="basic" className="text-xs">{t('model.form.tabs.basicInfo')}</TabsTrigger>
            <TabsTrigger value="capabilities" className="text-xs">{t('model.form.tabs.capabilities')}</TabsTrigger>
            <TabsTrigger value="limits" className="text-xs">{t('model.form.tabs.limits')}</TabsTrigger>
            <TabsTrigger value="pricing" className="text-xs">{t('model.form.tabs.pricing')}</TabsTrigger>
            <TabsTrigger value="diagnostics" className="text-xs">{t('model.form.tabs.diagnostics')}</TabsTrigger>
          </TabsList>

          <TabsContent value="basic" className="mt-4 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t('model.form.sections.identity.title')}</CardTitle>
                <CardDescription>{t('model.form.sections.identity.description')}</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <Field label={t('model.form.fields.modelRef')} value={modelRef} readOnly />
                <Field label={t('model.form.fields.modelId')} value={formData.modelId} readOnly={Boolean(formData.id)} onChange={(value) => updateField('modelId', value)} />
                <Field label={t('model.form.fields.displayName')} value={formData.displayName || ''} onChange={(value) => updateField('displayName', value)} />
                <Field label={t('model.form.fields.providerId')} value={formData.providerId} readOnly />
                <Field label={t('model.form.fields.providerKind')} value={formData.providerKind || ''} readOnly />
                <SelectField
                  label={t('model.form.fields.status')}
                  value={formData.status || (formData.enabled ? 'active' : 'disabled')}
                  options={['active', 'disabled', 'error']}
                  onChange={(value) => updateForm((current) => ({ ...current, status: value, enabled: value === 'active' }))}
                />
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="model-description">{t('model.form.fields.description')}</Label>
                  <Textarea id="model-description" value={formData.description || ''} onChange={(event) => updateField('description', event.target.value)} />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t('model.form.sections.source.title')}</CardTitle>
                <CardDescription>{t('model.form.sections.source.description')}</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <SelectField label={t('model.form.fields.source')} value={formData.source || 'local'} options={['platform', 'local', 'catalog', 'manual', 'override']} onChange={(value) => updateField('source', value)} />
                <Field label={t('model.form.fields.platformModelId')} value={formData.platformModelId || ''} onChange={(value) => updateField('platformModelId', value)} />
                <SelectField label={t('model.form.fields.lifecycle')} value={formData.lifecycle || 'stable'} options={['stable', 'preview', 'deprecated', 'retired']} onChange={(value) => updateField('lifecycle', value)} />
                <Field label={t('model.form.fields.lastSeenAt')} value={formData.lastSyncedAt || ''} onChange={(value) => updateField('lastSyncedAt', value)} />
                <Field label={t('model.form.fields.architectureModality')} value={formData.architecture?.modality || ''} onChange={(value) => updateArchitecture({ modality: value })} />
                <SelectField label={t('model.form.fields.tokenizer')} value={formData.architecture?.tokenizer || 'GPT'} options={['GPT', 'Claude', 'Gemini', 'Qwen', 'Custom']} onChange={(value) => updateArchitecture({ tokenizer: value })} />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="capabilities" className="mt-4 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t('model.form.sections.capabilityMatrix.title')}</CardTitle>
                <CardDescription>{t('model.form.sections.capabilityMatrix.description')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800">
                  {t('model.form.capabilitySourceNotice')}
                </div>
                <div className="space-y-2">
                  {CAPABILITY_KEYS.map((key) => {
                    const row = formData.capabilityMatrix?.[key] || {}
                    return (
                      <div key={key} className="grid grid-cols-[1fr_auto_auto] items-center gap-3 rounded-md border p-3">
                        <div className="min-w-0">
                          <div className="font-medium">{key}</div>
                          <div className="mt-1 flex flex-wrap gap-1 text-xs">
                            <Badge variant="secondary">catalog: {formatCapabilitySupport(row.catalog)}</Badge>
                            <Badge variant="secondary">diagnostics: {formatCapabilitySupport(row.diagnostics)}</Badge>
                            <Badge variant="secondary">runtime: {formatCapabilitySupport(row.runtime)}</Badge>
                          </div>
                        </div>
                        <Switch checked={row.merged === true} disabled aria-label={`${key} merged`} />
                        <NativeSelect
                          aria-label={`${key} override`}
                          className="w-[150px]"
                          value={row.user_override || 'auto'}
                          onChange={(event) => updateCapability(key, { user_override: event.target.value })}
                        >
                          <option value="auto">{t('model.form.options.override.auto')}</option>
                          <option value="force_on">{t('model.form.options.override.forceOn')}</option>
                          <option value="force_off">{t('model.form.options.override.forceOff')}</option>
                          <option value="enable_after_diagnostics">{t('model.form.options.override.enableAfterDiagnostics')}</option>
                        </NativeSelect>
                      </div>
                    )
                  })}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t('model.form.sections.modalities.title')}</CardTitle>
                <CardDescription>{t('model.form.sections.modalities.description')}</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <TextareaField label={t('model.form.fields.inputModalities')} value={splitLines(formData.architecture?.input_modalities)} onChange={(value) => updateArchitecture({ input_modalities: lines(value) })} />
                <TextareaField label={t('model.form.fields.outputModalities')} value={splitLines(formData.architecture?.output_modalities)} onChange={(value) => updateArchitecture({ output_modalities: lines(value) })} />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="limits" className="mt-4 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t('model.form.sections.limits.title')}</CardTitle>
                <CardDescription>{t('model.form.sections.limits.description')}</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <NumberField label={t('model.form.fields.contextWindow')} value={formData.contextWindow} onChange={(value) => updateField('contextWindow', value)} />
                <NumberField label={t('model.form.fields.maxOutputTokens')} value={formData.maxOutputTokens} onChange={(value) => updateField('maxOutputTokens', value)} />
                <NumberField label={t('model.form.fields.maxInputFiles')} value={formData.parameterConfig?.max_input_files} onChange={(value) => updateParameterConfig({ max_input_files: value })} />
                <NumberField label={t('model.form.fields.maxImageCount')} value={formData.parameterConfig?.max_image_count} onChange={(value) => updateParameterConfig({ max_image_count: value })} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t('model.form.sections.parameters.title')}</CardTitle>
                <CardDescription>{t('model.form.sections.parameters.description')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-2 sm:grid-cols-2">
                  {PARAMETER_KEYS.map((key) => {
                    const selected = Boolean(formData.parameterConfig?.supported_parameters?.includes(key))
                    return (
                      <label key={key} className="flex items-center justify-between rounded-md border p-3 text-sm">
                        <span>{key}</span>
                        <Switch
                          checked={selected}
                          onCheckedChange={(checked) => {
                            const current = formData.parameterConfig?.supported_parameters || []
                            updateParameterConfig({ supported_parameters: checked ? unique([...current, key]) : current.filter((item) => item !== key) })
                          }}
                        />
                      </label>
                    )
                  })}
                </div>
                <div className="grid gap-4 sm:grid-cols-3">
                  <NumberField label={t('model.form.fields.defaultTemperature')} value={formData.parameterConfig?.default_parameters?.temperature} onChange={(value) => updateDefaultParameter('temperature', value)} />
                  <NumberField label={t('model.form.fields.defaultTopP')} value={formData.parameterConfig?.default_parameters?.top_p} onChange={(value) => updateDefaultParameter('top_p', value)} />
                  <NumberField label={t('model.form.fields.defaultMaxTokens')} value={formData.parameterConfig?.default_parameters?.max_tokens} onChange={(value) => updateDefaultParameter('max_tokens', value)} />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="pricing" className="mt-4 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t('model.form.sections.pricing.title')}</CardTitle>
                <CardDescription>{t('model.form.sections.pricing.description')}</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <SelectField label={t('model.form.fields.currency')} value={formData.pricing?.currency || 'USD'} options={['USD', 'CNY', 'EUR']} onChange={(value) => updatePricing({ currency: value })} />
                <SelectField label={t('model.form.fields.pricingSource')} value={formData.pricing?.pricing_source || 'manual'} options={['catalog', 'manual', 'unknown']} onChange={(value) => updatePricing({ pricing_source: value })} />
                <NumberField label={t('model.form.fields.promptPrice')} value={formData.pricing?.prompt?.amount} onChange={(value) => updatePricingBucket('prompt', { amount: value })} />
                <NumberField label={t('model.form.fields.completionPrice')} value={formData.pricing?.completion?.amount} onChange={(value) => updatePricingBucket('completion', { amount: value })} />
                <NumberField label={t('model.form.fields.imagePrice')} value={formData.pricing?.image?.amount} onChange={(value) => updatePricingBucket('image', { amount: value })} />
                <NumberField label={t('model.form.fields.requestPrice')} value={formData.pricing?.request?.amount} onChange={(value) => updatePricingBucket('request', { amount: value })} />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="diagnostics" className="mt-4 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t('model.form.sections.diagnostics.title')}</CardTitle>
                <CardDescription>{t('model.form.sections.diagnostics.description')}</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <SelectField label={t('model.form.fields.lastTestStatus')} value={formData.diagnostics?.last_test_status || 'skipped'} options={['passed', 'failed', 'skipped']} onChange={(value) => updateDiagnostics({ last_test_status: value })} />
                <Field label={t('model.form.fields.lastTestAt')} value={formData.diagnostics?.last_test_at || ''} onChange={(value) => updateDiagnostics({ last_test_at: value })} />
                <TextareaField label={t('model.form.fields.lastTestError')} value={formData.diagnostics?.last_test_error || ''} onChange={(value) => updateDiagnostics({ last_test_error: value })} className="sm:col-span-2" />
                <SelectField label={t('model.form.fields.testMode')} value={formData.diagnostics?.test_mode || 'chat'} options={['chat', 'embedding', 'vision', 'tool_calling']} onChange={(value) => updateDiagnostics({ test_mode: value })} />
                <NumberField label={t('model.form.fields.timeoutMs')} value={formData.diagnostics?.timeout_ms} onChange={(value) => updateDiagnostics({ timeout_ms: value })} />
                <TextareaField label={t('model.form.fields.testPrompt')} value={formData.diagnostics?.test_prompt || ''} onChange={(value) => updateDiagnostics({ test_prompt: value })} className="sm:col-span-2" />
                <TextareaField label={t('model.form.fields.overrideReason')} value={formData.diagnostics?.override_reason || ''} onChange={(value) => updateDiagnostics({ override_reason: value })} className="sm:col-span-2" />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t('model.form.sections.runtimeStats.title')}</CardTitle>
                <CardDescription>{t('model.form.sections.runtimeStats.description')}</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <NumberField label={t('model.form.fields.monthCalls')} value={formData.diagnostics?.runtime_stats?.month_calls} onChange={(value) => updateDiagnosticsObject('runtime_stats', { month_calls: value })} />
                <NumberField label={t('model.form.fields.monthTokens')} value={formData.diagnostics?.runtime_stats?.month_tokens} onChange={(value) => updateDiagnosticsObject('runtime_stats', { month_tokens: value })} />
                <NumberField label={t('model.form.fields.avgLatencyMs')} value={formData.diagnostics?.runtime_stats?.avg_latency_ms} onChange={(value) => updateDiagnosticsObject('runtime_stats', { avg_latency_ms: value })} />
                <NumberField label={t('model.form.fields.errorRate')} value={formData.diagnostics?.runtime_stats?.error_rate} onChange={(value) => updateDiagnosticsObject('runtime_stats', { error_rate: value })} />
                <SelectField label={t('model.form.fields.supportCatalog')} value={String(formData.diagnostics?.support?.catalog || 'unknown')} options={['trusted', 'untrusted', 'unknown']} onChange={(value) => updateDiagnosticsObject('support', { catalog: value })} />
                <SelectField label={t('model.form.fields.supportDiagnostics')} value={String(formData.diagnostics?.support?.diagnostics || 'unknown')} options={['passed', 'failed', 'partial', 'skipped', 'unknown']} onChange={(value) => updateDiagnosticsObject('support', { diagnostics: value })} />
                <SelectField label={t('model.form.fields.supportRuntime')} value={String(formData.diagnostics?.support?.runtime || 'unknown')} options={['callable', 'not_callable', 'unknown']} onChange={(value) => updateDiagnosticsObject('support', { runtime: value })} />
                <TextareaField label={t('model.form.fields.rawMeta')} value={rawMetaText} onChange={updateRawMeta} className="sm:col-span-2" />
                <TextareaField label={t('model.form.fields.userOverridesJson')} value={userOverridesText} onChange={updateUserOverrides} className="sm:col-span-2" />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      <DrawerFooter className="border-t">
        <div className="flex justify-between gap-4">
          <DrawerClose asChild>
            <Button variant="outline" onClick={onCancel}>{t('common.operation.cancel')}</Button>
          </DrawerClose>
          <Button onClick={(event) => {
            event.preventDefault()
            onSave(event)
          }}>
            {t('common.operation.save')}
          </Button>
        </div>
      </DrawerFooter>
    </form>
  )
}

function Field({ label, value, onChange, readOnly }: { label: string; value: string; onChange?: (value: string) => void; readOnly?: boolean }) {
  const id = useMemo(() => `model-${label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`, [label])
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} value={value} readOnly={readOnly} onChange={(event) => onChange?.(event.target.value)} />
    </div>
  )
}

function NumberField({ label, value, onChange }: { label: string; value?: number; onChange: (value?: number) => void }) {
  const id = useMemo(() => `model-${label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`, [label])
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} type="number" value={value ?? ''} onChange={(event) => onChange(numberValue(event.target.value))} />
    </div>
  )
}

function SelectField({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  const id = useMemo(() => `model-${label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`, [label])
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <NativeSelect id={id} className="w-full" value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => <option key={option} value={option}>{option}</option>)}
      </NativeSelect>
    </div>
  )
}

function TextareaField({ label, value, onChange, className }: { label: string; value: string; onChange: (value: string) => void; className?: string }) {
  const id = useMemo(() => `model-${label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`, [label])
  return (
    <div className={`space-y-2 ${className || ''}`}>
      <Label htmlFor={id}>{label}</Label>
      <Textarea id={id} value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  )
}
