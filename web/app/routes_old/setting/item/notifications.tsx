import { useCallback, useEffect, useState } from 'react'
import { Bell, CheckCircle2, Loader2, Plus, Send, Trash2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { toast } from '@/hooks/use-toast'
import { useTranslation } from '@/i18n'
import {
  createNotificationEndpoint,
  deleteNotificationEndpoint,
  getNotificationPreferences,
  listNotificationDeliveries,
  listNotificationEndpoints,
  testNotificationEndpoint,
  updateNotificationEndpoint,
  updateNotificationPreferences,
  type NotificationDeliveryMode,
  type NotificationEndpoint,
  type NotificationEndpointKind,
  type NotificationPreference,
} from '@/services/notification-service'

const CATEGORY_KEYS = ['system', 'security', 'account', 'agent', 'workflow', 'task'] as const
const ENDPOINT_KINDS: NotificationEndpointKind[] = [
  'email',
  'webhook',
  'slack',
  'teams',
  'discord',
  'telegram',
  'other',
]

function Page() {
  const { t: translate } = useTranslation()
  const t = useCallback(
    (key: string) => translate(key.replace(':', '.') as Parameters<typeof translate>[0]),
    [translate],
  )
  const [preferences, setPreferences] = useState<NotificationPreference | null>(null)
  const [endpoints, setEndpoints] = useState<NotificationEndpoint[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [creating, setCreating] = useState(false)
  const [testingId, setTestingId] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [kind, setKind] = useState<NotificationEndpointKind>('email')
  const [url, setUrl] = useState('')

  const loadSettings = useCallback(async () => {
    setLoading(true)
    try {
      const [nextPreferences, nextEndpoints] = await Promise.all([
        getNotificationPreferences(),
        listNotificationEndpoints(),
      ])
      setPreferences(nextPreferences)
      setEndpoints(nextEndpoints)
    } catch {
      toast({
        title: t('notification:settings.messages.loadFailed'),
        type: 'error',
      })
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    void loadSettings()
  }, [loadSettings])

  const savePreferences = async () => {
    if (!preferences) return
    setSaving(true)
    try {
      const updated = await updateNotificationPreferences({
        delivery_mode: preferences.delivery_mode,
        categories: { ...preferences.categories, security: true },
        quiet_hours_enabled: preferences.quiet_hours_enabled,
        quiet_hours_start: preferences.quiet_hours_start,
        quiet_hours_end: preferences.quiet_hours_end,
        timezone: preferences.timezone,
      })
      setPreferences(updated)
      toast({ title: t('notification:settings.messages.saved') })
    } catch {
      toast({ title: t('notification:settings.messages.saveFailed'), type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const addEndpoint = async () => {
    if (!name.trim() || !url.trim()) return
    setCreating(true)
    try {
      const endpoint = await createNotificationEndpoint({ name: name.trim(), kind, url: url.trim() })
      setEndpoints((current) => [...current, endpoint])
      setName('')
      setUrl('')
      toast({ title: t('notification:settings.messages.endpointAdded') })
    } catch {
      toast({ title: t('notification:settings.messages.endpointFailed'), type: 'error' })
    } finally {
      setCreating(false)
    }
  }

  const toggleEndpoint = async (endpoint: NotificationEndpoint) => {
    const updated = await updateNotificationEndpoint(endpoint.id, {
      status: endpoint.status === 'active' ? 'disabled' : 'active',
    })
    setEndpoints((current) => current.map((item) => item.id === updated.id ? updated : item))
  }

  const removeEndpoint = async (endpointId: string) => {
    await deleteNotificationEndpoint(endpointId)
    setEndpoints((current) => current.filter((item) => item.id !== endpointId))
  }

  const testEndpoint = async (endpointId: string) => {
    setTestingId(endpointId)
    try {
      const queued = await testNotificationEndpoint(endpointId)
      let status = queued.status
      for (let attempt = 0; attempt < 10 && !['sent', 'failed'].includes(status); attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000))
        const deliveries = await listNotificationDeliveries(queued.notification_id)
        status = deliveries.find((item) => item.id === queued.id)?.status ?? status
      }
      toast({
        title: status === 'sent'
          ? t('notification:settings.messages.testSent')
          : status === 'failed'
            ? t('notification:settings.messages.testFailed')
            : t('notification:settings.messages.testQueued'),
        type: status === 'failed' ? 'error' : 'default',
      })
    } catch {
      toast({ title: t('notification:settings.messages.testFailed'), type: 'error' })
    } finally {
      setTestingId(null)
    }
  }

  if (loading || !preferences) {
    return (
      <div className="flex min-h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col gap-6 p-4 md:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="flex items-center gap-2 text-lg font-bold tracking-tight">
            <Bell className="h-5 w-5" />
            {t('notification:settings.title')}
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">{t('notification:settings.description')}</p>
        </div>
        <Button onClick={savePreferences} disabled={saving}>
          {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
          {t('notification:settings.save')}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('notification:settings.delivery.title')}</CardTitle>
          <CardDescription>{t('notification:settings.delivery.description')}</CardDescription>
        </CardHeader>
        <CardContent>
          <RadioGroup
            value={preferences.delivery_mode}
            onValueChange={(value) => setPreferences({ ...preferences, delivery_mode: value as NotificationDeliveryMode })}
            className="grid gap-3 md:grid-cols-3"
          >
            {(['in_app', 'in_app_email', 'in_app_all'] as NotificationDeliveryMode[]).map((mode) => (
              <Label key={mode} htmlFor={mode} className="flex cursor-pointer items-start gap-3 rounded-lg border p-4">
                <RadioGroupItem value={mode} id={mode} className="mt-0.5" />
                <span>
                  <span className="block font-medium">{t(`notification:settings.delivery.${mode}.title`)}</span>
                  <span className="mt-1 block text-sm font-normal text-muted-foreground">
                    {t(`notification:settings.delivery.${mode}.description`)}
                  </span>
                </span>
              </Label>
            ))}
          </RadioGroup>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('notification:settings.categories.title')}</CardTitle>
          <CardDescription>{t('notification:settings.categories.description')}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          {CATEGORY_KEYS.map((category) => {
            const locked = category === 'security'
            return (
              <div key={category} className="flex items-center justify-between gap-4 rounded-lg border p-4">
                <div className="min-w-0">
                  <Label>{t(`notification:settings.categories.${category}`)}</Label>
                  {locked && <p className="mt-1 text-xs text-muted-foreground">{t('notification:settings.categories.required')}</p>}
                </div>
                <Switch
                  checked={locked || Boolean(preferences.categories[category])}
                  disabled={locked}
                  onCheckedChange={(checked) => setPreferences({
                    ...preferences,
                    categories: { ...preferences.categories, [category]: checked },
                  })}
                />
              </div>
            )
          })}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('notification:settings.quietHours.title')}</CardTitle>
          <CardDescription>{t('notification:settings.quietHours.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border p-4">
            <Label htmlFor="quiet-hours">{t('notification:settings.quietHours.enabled')}</Label>
            <Switch
              id="quiet-hours"
              checked={preferences.quiet_hours_enabled}
              onCheckedChange={(checked) => setPreferences({ ...preferences, quiet_hours_enabled: checked })}
            />
          </div>
          {preferences.quiet_hours_enabled && (
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="quiet-start">{t('notification:settings.quietHours.start')}</Label>
                <Input id="quiet-start" type="time" value={preferences.quiet_hours_start} onChange={(event) => setPreferences({ ...preferences, quiet_hours_start: event.target.value })} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="quiet-end">{t('notification:settings.quietHours.end')}</Label>
                <Input id="quiet-end" type="time" value={preferences.quiet_hours_end} onChange={(event) => setPreferences({ ...preferences, quiet_hours_end: event.target.value })} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="timezone">{t('notification:settings.quietHours.timezone')}</Label>
                <Input id="timezone" value={preferences.timezone} onChange={(event) => setPreferences({ ...preferences, timezone: event.target.value })} placeholder="Asia/Shanghai" />
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('notification:settings.endpoints.title')}</CardTitle>
          <CardDescription>{t('notification:settings.endpoints.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-3 rounded-lg border p-4 md:grid-cols-[1fr_160px_2fr_auto] md:items-end">
            <div className="space-y-2">
              <Label htmlFor="endpoint-name">{t('notification:settings.endpoints.name')}</Label>
              <Input id="endpoint-name" value={name} onChange={(event) => setName(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>{t('notification:settings.endpoints.kind')}</Label>
              <Select value={kind} onValueChange={(value) => setKind(value as NotificationEndpointKind)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ENDPOINT_KINDS.map((item) => <SelectItem key={item} value={item}>{item}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="endpoint-url">{t('notification:settings.endpoints.url')}</Label>
              <Input id="endpoint-url" type="password" autoComplete="off" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="mailto://..." />
            </div>
            <Button onClick={addEndpoint} disabled={creating || !name.trim() || !url.trim()}>
              {creating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
              {t('notification:settings.endpoints.add')}
            </Button>
          </div>

          <div className="space-y-3">
            {endpoints.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">{t('notification:settings.endpoints.empty')}</p>}
            {endpoints.map((endpoint) => (
              <div key={endpoint.id} className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{endpoint.name}</span>
                    <Badge variant="outline">{endpoint.kind}</Badge>
                    <Badge variant={endpoint.status === 'active' ? 'default' : 'secondary'}>{endpoint.status}</Badge>
                  </div>
                  <p className="mt-1 truncate text-sm text-muted-foreground">{endpoint.display_target}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Switch checked={endpoint.status === 'active'} onCheckedChange={() => void toggleEndpoint(endpoint)} />
                  <Button variant="outline" size="sm" disabled={testingId === endpoint.id || endpoint.status !== 'active'} onClick={() => void testEndpoint(endpoint.id)}>
                    {testingId === endpoint.id ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                    {t('notification:settings.endpoints.test')}
                  </Button>
                  <Button variant="ghost" size="icon" aria-label={t('notification:settings.endpoints.delete')} onClick={() => void removeEndpoint(endpoint.id)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default Page
