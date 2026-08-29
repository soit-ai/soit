import { useEffect, useMemo, useState } from 'react'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { NativeSelect } from '@/components/ui/native-select'
import { Key, Plus, Copy, RefreshCw, Eye, EyeOff, AlertTriangle, ShieldCheck } from 'lucide-react'
import { toast } from '@/hooks/use-toast'
import { useTranslation } from '@/i18n'
import type { TFunction } from '@/i18n/types'
import {
  createApiKey,
  listApiKeys,
  revokeApiKey,
  rotateApiKey,
  type ApiKeyItem,
  type ApiKeyScope,
} from '@/services/api-key-service'
import {
  getWorkspaceEgressPolicy,
  getWorkspaceUsagePolicy,
  listEgressPolicyAudits,
  updateWorkspaceEgressPolicy,
  updateWorkspaceUsagePolicy,
  type EgressPolicyAudit,
} from '@/services/security-service'
import { formatDateTime, isoToZonedDate } from '@/utils/date-time'

const scopeLabel = (t: TFunction, scope: string) => {
  if (scope === 'read') return t('system.settings.api.keys.scopes.read')
  if (scope === 'write') return t('system.settings.api.keys.scopes.write')
  if (scope === 'admin') return t('system.settings.api.keys.scopes.admin')
  return scope
}

type PolicyFormState = {
  llm_rate_limit_per_minute: string
  tool_rate_limit_per_minute: string
  llm_daily_quota: string
  tool_daily_quota: string
}

type EgressFormState = {
  allowlist: string
  blocklist: string
}

const parseNumber = (value: string): number | null => {
  if (!value.trim()) {
    return null
  }
  const num = Number(value)
  return Number.isNaN(num) ? null : num
}

const parseDomainList = (value: string): string[] => {
  return value
    .split(/[\n,]/)
    .map(item => item.trim())
    .filter(Boolean)
}

const formatDomainList = (items?: string[]) => {
  return (items || []).join('\n')
}

const formatTimestamp = (value?: string | null) => {
  if (!value) {
    return '-'
  }
  return formatDateTime(isoToZonedDate(value))
}

function Page() {
  const { t } = useTranslation()
  const [apiKeys, setApiKeys] = useState<ApiKeyItem[]>([])
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [showKey, setShowKey] = useState<Record<string, boolean>>({})
  const [revealedKeys, setRevealedKeys] = useState<Record<string, string>>({})
  const [newKeyName, setNewKeyName] = useState('')
  // Scope and lifetime are required by the API: a key must never silently
  // inherit its owner's full role or live forever.
  const [newKeyScope, setNewKeyScope] = useState<ApiKeyScope>('read')
  const [newKeyExpiresInDays, setNewKeyExpiresInDays] = useState(90)
  const [policyLoading, setPolicyLoading] = useState(false)
  const [policyForm, setPolicyForm] = useState<PolicyFormState>({
    llm_rate_limit_per_minute: '',
    tool_rate_limit_per_minute: '',
    llm_daily_quota: '',
    tool_daily_quota: '',
  })
  const [egressLoading, setEgressLoading] = useState(false)
  const [egressAuditLoading, setEgressAuditLoading] = useState(false)
  const [egressForm, setEgressForm] = useState<EgressFormState>({
    allowlist: '',
    blocklist: '',
  })
  const [egressAudits, setEgressAudits] = useState<EgressPolicyAudit[]>([])

  const fetchApiKeys = async () => {
    try {
      setLoading(true)
      const data = await listApiKeys({ page_size: 100 })
      setApiKeys(data.items || [])
    } catch (error) {
      toast({
        title: t('system.settings.api.toast.errorTitle'),
        description: t('system.settings.api.toast.fetchKeysError'),
        type: 'error',
      })
    } finally {
      setLoading(false)
    }
  }

  const fetchUsagePolicy = async () => {
    try {
      const data = await getWorkspaceUsagePolicy()
      setPolicyForm({
        llm_rate_limit_per_minute: data.llm_rate_limit_per_minute?.toString() ?? '',
        tool_rate_limit_per_minute: data.tool_rate_limit_per_minute?.toString() ?? '',
        llm_daily_quota: data.llm_daily_quota?.toString() ?? '',
        tool_daily_quota: data.tool_daily_quota?.toString() ?? '',
      })
    } catch (error) {
      toast({
        title: t('system.settings.api.toast.errorTitle'),
        description: t('system.settings.api.toast.fetchUsageError'),
        type: 'error',
      })
    }
  }

  const fetchEgressPolicy = async () => {
    try {
      const data = await getWorkspaceEgressPolicy()
      setEgressForm({
        allowlist: formatDomainList(data.allowlist),
        blocklist: formatDomainList(data.blocklist),
      })
    } catch (error) {
      toast({
        title: t('system.settings.api.toast.errorTitle'),
        description: t('system.settings.api.toast.fetchEgressError'),
        type: 'error',
      })
    }
  }

  const fetchEgressAudits = async () => {
    try {
      setEgressAuditLoading(true)
      const data = await listEgressPolicyAudits({ scope: 'workspace', page_size: 20 })
      setEgressAudits(data.items || [])
    } catch (error) {
      toast({
        title: t('system.settings.api.toast.errorTitle'),
        description: t('system.settings.api.toast.fetchEgressAuditError'),
        type: 'error',
      })
    } finally {
      setEgressAuditLoading(false)
    }
  }

  useEffect(() => {
    fetchApiKeys()
    fetchUsagePolicy()
    fetchEgressPolicy()
    fetchEgressAudits()
  }, [])

  const handleCopyKey = (value: string) => {
    navigator.clipboard.writeText(value)
    toast({
      title: t('system.settings.api.toast.copiedTitle'),
      description: t('system.settings.api.toast.copiedDescription'),
    })
  }

  const toggleShowKey = (id: string) => {
    setShowKey(prev => ({
      ...prev,
      [id]: !prev[id],
    }))
  }

  const handleCreateKey = async () => {
    if (!newKeyName.trim()) {
      toast({
        title: t('system.settings.api.toast.errorTitle'),
        description: t('system.settings.api.toast.nameRequired'),
        type: 'error',
      })
      return
    }
    try {
      setActionLoading('create')
      const result = await createApiKey({
        name: newKeyName,
        scopes: [newKeyScope],
        expires_in_days: newKeyExpiresInDays,
      })
      setApiKeys(prev => [result.item, ...prev])
      setRevealedKeys(prev => ({ ...prev, [result.item.id]: result.api_key }))
      setNewKeyName('')
      toast({
        title: t('system.settings.api.toast.createdTitle'),
        description: t('system.settings.api.toast.createdDescription'),
      })
    } catch (error) {
      toast({
        title: t('system.settings.api.toast.errorTitle'),
        description: t('system.settings.api.toast.createError'),
        type: 'error',
      })
    } finally {
      setActionLoading(null)
    }
  }

  const handleRevokeKey = async (id: string) => {
    try {
      setActionLoading(id)
      const result = await revokeApiKey(id)
      setApiKeys(prev => prev.map(item => (item.id === id ? result : item)))
      toast({
        title: t('system.settings.api.toast.revokedTitle'),
        description: t('system.settings.api.toast.revokedDescription'),
      })
    } catch (error) {
      toast({
        title: t('system.settings.api.toast.errorTitle'),
        description: t('system.settings.api.toast.revokeError'),
        type: 'error',
      })
    } finally {
      setActionLoading(null)
    }
  }

  const handleRotateKey = async (id: string) => {
    try {
      setActionLoading(id)
      const result = await rotateApiKey(id)
      setApiKeys(prev => prev.map(item => (item.id === id ? result.item : item)))
      setRevealedKeys(prev => ({ ...prev, [id]: result.api_key }))
      toast({
        title: t('system.settings.api.toast.rotatedTitle'),
        description: t('system.settings.api.toast.rotatedDescription'),
      })
    } catch (error) {
      toast({
        title: t('system.settings.api.toast.errorTitle'),
        description: t('system.settings.api.toast.rotateError'),
        type: 'error',
      })
    } finally {
      setActionLoading(null)
    }
  }

  const handleSavePolicy = async () => {
    try {
      setPolicyLoading(true)
      await updateWorkspaceUsagePolicy({
        llm_rate_limit_per_minute: parseNumber(policyForm.llm_rate_limit_per_minute),
        tool_rate_limit_per_minute: parseNumber(policyForm.tool_rate_limit_per_minute),
        llm_daily_quota: parseNumber(policyForm.llm_daily_quota),
        tool_daily_quota: parseNumber(policyForm.tool_daily_quota),
      })
      toast({
        title: t('system.settings.api.toast.savedTitle'),
        description: t('system.settings.api.toast.usageSaved'),
      })
    } catch (error) {
      toast({
        title: t('system.settings.api.toast.errorTitle'),
        description: t('system.settings.api.toast.usageSaveError'),
        type: 'error',
      })
    } finally {
      setPolicyLoading(false)
    }
  }

  const handleSaveEgressPolicy = async () => {
    try {
      setEgressLoading(true)
      const result = await updateWorkspaceEgressPolicy({
        allowlist: parseDomainList(egressForm.allowlist),
        blocklist: parseDomainList(egressForm.blocklist),
      })
      setEgressForm({
        allowlist: formatDomainList(result.allowlist),
        blocklist: formatDomainList(result.blocklist),
      })
      await fetchEgressAudits()
      toast({
        title: t('system.settings.api.toast.savedTitle'),
        description: t('system.settings.api.toast.egressSaved'),
      })
    } catch (error) {
      toast({
        title: t('system.settings.api.toast.errorTitle'),
        description: t('system.settings.api.toast.egressSaveError'),
        type: 'error',
      })
    } finally {
      setEgressLoading(false)
    }
  }

  const sortedKeys = useMemo(() => {
    return [...apiKeys].sort((a, b) => b.created_at.localeCompare(a.created_at))
  }, [apiKeys])

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div>
        <h3 className="text-lg font-bold tracking-tight">{t('system.settings.api.title')}</h3>
        <p className="text-sm text-muted-foreground mt-1">{t('system.settings.api.description')}</p>
      </div>

      <Tabs defaultValue="keys" className="w-full">
        <TabsList className="mb-4 grid w-full max-w-xl grid-cols-3">
          <TabsTrigger value="keys">{t('system.settings.api.tabs.keys')}</TabsTrigger>
          <TabsTrigger value="limits">{t('system.settings.api.tabs.limits')}</TabsTrigger>
          <TabsTrigger value="egress">{t('system.settings.api.tabs.egress')}</TabsTrigger>
        </TabsList>

        <TabsContent value="keys">
          <Card>
            <CardHeader>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <CardTitle>{t('system.settings.api.keys.title')}</CardTitle>
                  <CardDescription>{t('system.settings.api.keys.description')}</CardDescription>
                </div>
                <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
                  <Input
                    value={newKeyName}
                    onChange={(e) => setNewKeyName(e.target.value)}
                    placeholder={t('system.settings.api.keys.namePlaceholder')}
                    className="w-full sm:w-48"
                  />
                  <NativeSelect
                    aria-label={t('system.settings.api.keys.scopeLabel')}
                    className="w-full sm:w-32"
                    value={newKeyScope}
                    onChange={(e) => setNewKeyScope(e.target.value as ApiKeyScope)}
                  >
                    <option value="read">{t('system.settings.api.keys.scopes.read')}</option>
                    <option value="write">{t('system.settings.api.keys.scopes.write')}</option>
                    <option value="admin">{t('system.settings.api.keys.scopes.admin')}</option>
                  </NativeSelect>
                  <NativeSelect
                    aria-label={t('system.settings.api.keys.expiresLabel')}
                    className="w-full sm:w-32"
                    value={String(newKeyExpiresInDays)}
                    onChange={(e) => setNewKeyExpiresInDays(Number(e.target.value))}
                  >
                    <option value="30">{t('system.settings.api.keys.expiresDays', { days: 30 })}</option>
                    <option value="90">{t('system.settings.api.keys.expiresDays', { days: 90 })}</option>
                    <option value="180">{t('system.settings.api.keys.expiresDays', { days: 180 })}</option>
                    <option value="365">{t('system.settings.api.keys.expiresDays', { days: 365 })}</option>
                  </NativeSelect>
                  <Button onClick={handleCreateKey} disabled={actionLoading === 'create'}>
                    <Plus className="mr-2 h-4 w-4" />
                    {t('system.settings.api.keys.create')}
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {loading && <div className="text-sm text-muted-foreground">{t('system.settings.api.keys.loading')}</div>}
              {!loading && sortedKeys.length === 0 && (
                <div className="text-sm text-muted-foreground">{t('system.settings.api.keys.empty')}</div>
              )}
              <div className="space-y-4">
                {sortedKeys.map((apiKey) => {
                  const rawKey = revealedKeys[apiKey.id]
                  const displayValue = rawKey || `${apiKey.key_prefix}...`
                  const isVisible = showKey[apiKey.id] && rawKey
                  const statusLabel = apiKey.status === 'active'
                    ? t('system.settings.api.keys.statusActive')
                    : t('system.settings.api.keys.statusRevoked')
                  return (
                    <div key={apiKey.id} className="flex flex-col space-y-2 rounded-md border p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <Key className="h-5 w-5 text-muted-foreground" />
                          <span className="font-medium">{apiKey.name}</span>
                          <Badge variant={apiKey.status === 'active' ? 'default' : 'destructive'}>
                            {statusLabel}
                          </Badge>
                          {(apiKey.scopes ?? []).map((scope) => (
                            <Badge key={scope} variant="outline">
                              {scopeLabel(t, scope)}
                            </Badge>
                          ))}
                        </div>
                        <div className="flex items-center gap-2">
                          {rawKey && (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => toggleShowKey(apiKey.id)}
                              title={isVisible ? t('system.settings.api.keys.hide') : t('system.settings.api.keys.show')}
                            >
                              {isVisible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleCopyKey(rawKey || displayValue)}
                            title={t('system.settings.api.keys.copy')}
                          >
                            <Copy className="h-4 w-4" />
                          </Button>
                          {apiKey.status === 'active' && (
                            <>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleRotateKey(apiKey.id)}
                                disabled={actionLoading === apiKey.id}
                              >
                                <RefreshCw className="mr-2 h-4 w-4" />
                                {t('system.settings.api.keys.rotate')}
                              </Button>
                              <Button
                                variant="destructive"
                                size="sm"
                                onClick={() => handleRevokeKey(apiKey.id)}
                                disabled={actionLoading === apiKey.id}
                              >
                                {t('system.settings.api.keys.revoke')}
                              </Button>
                            </>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-4 text-sm text-muted-foreground">
                        <div className="font-mono bg-muted px-2 py-1 rounded">
                          {rawKey ? (isVisible ? rawKey : `${rawKey.slice(0, 6)}...${rawKey.slice(-4)}`) : displayValue}
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
                        <span>{t('system.settings.api.keys.createdAt', { value: apiKey.created_at })}</span>
                        <span>{t('system.settings.api.keys.expiresAt', { value: apiKey.expires_at || '-' })}</span>
                        <span>{t('system.settings.api.keys.lastUsedAt', { value: apiKey.last_used_at || '-' })}</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="limits">
          <Card>
            <CardHeader>
              <CardTitle>{t('system.settings.api.limits.title')}</CardTitle>
              <CardDescription>{t('system.settings.api.limits.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>{t('system.settings.api.limits.noticeTitle')}</AlertTitle>
                <AlertDescription>
                  {t('system.settings.api.limits.noticeDescription')}
                </AlertDescription>
              </Alert>

              <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="llm-rate-limit">{t('system.settings.api.limits.llmRateLimit')}</Label>
                  <Input
                    id="llm-rate-limit"
                    type="number"
                    value={policyForm.llm_rate_limit_per_minute}
                    onChange={(e) =>
                      setPolicyForm(prev => ({ ...prev, llm_rate_limit_per_minute: e.target.value }))
                    }
                    min="0"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="tool-rate-limit">{t('system.settings.api.limits.toolRateLimit')}</Label>
                  <Input
                    id="tool-rate-limit"
                    type="number"
                    value={policyForm.tool_rate_limit_per_minute}
                    onChange={(e) =>
                      setPolicyForm(prev => ({ ...prev, tool_rate_limit_per_minute: e.target.value }))
                    }
                    min="0"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="llm-daily-quota">{t('system.settings.api.limits.llmDailyQuota')}</Label>
                  <Input
                    id="llm-daily-quota"
                    type="number"
                    value={policyForm.llm_daily_quota}
                    onChange={(e) => setPolicyForm(prev => ({ ...prev, llm_daily_quota: e.target.value }))}
                    min="0"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="tool-daily-quota">{t('system.settings.api.limits.toolDailyQuota')}</Label>
                  <Input
                    id="tool-daily-quota"
                    type="number"
                    value={policyForm.tool_daily_quota}
                    onChange={(e) => setPolicyForm(prev => ({ ...prev, tool_daily_quota: e.target.value }))}
                    min="0"
                  />
                </div>
              </div>
            </CardContent>
            <CardFooter className="flex justify-end">
              <Button onClick={handleSavePolicy} disabled={policyLoading}>
                {t('system.settings.api.limits.save')}
              </Button>
            </CardFooter>
          </Card>
        </TabsContent>

        <TabsContent value="egress">
          <div className="grid gap-4 xl:grid-cols-[1fr_0.95fr]">
            <Card>
              <CardHeader>
                <CardTitle>{t('system.settings.api.egress.title')}</CardTitle>
                <CardDescription>{t('system.settings.api.egress.description')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <Alert>
                  <ShieldCheck className="h-4 w-4" />
                  <AlertTitle>{t('system.settings.api.egress.noticeTitle')}</AlertTitle>
                  <AlertDescription>
                    {t('system.settings.api.egress.noticeDescription')}
                  </AlertDescription>
                </Alert>

                <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="egress-allowlist">{t('system.settings.api.egress.allowlist')}</Label>
                    <Textarea
                      id="egress-allowlist"
                      value={egressForm.allowlist}
                      onChange={(e) => setEgressForm(prev => ({ ...prev, allowlist: e.target.value }))}
                      placeholder={'api.example.com\n*.trusted.internal'}
                      className="min-h-40 font-mono text-sm"
                    />
                    <p className="text-xs text-muted-foreground">{t('system.settings.api.egress.allowlistHint')}</p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="egress-blocklist">{t('system.settings.api.egress.blocklist')}</Label>
                    <Textarea
                      id="egress-blocklist"
                      value={egressForm.blocklist}
                      onChange={(e) => setEgressForm(prev => ({ ...prev, blocklist: e.target.value }))}
                      placeholder={'*.blocked.example\n169.254.169.254'}
                      className="min-h-40 font-mono text-sm"
                    />
                    <p className="text-xs text-muted-foreground">{t('system.settings.api.egress.blocklistHint')}</p>
                  </div>
                </div>
              </CardContent>
              <CardFooter className="flex justify-end">
                <Button onClick={handleSaveEgressPolicy} disabled={egressLoading}>
                  {t('system.settings.api.egress.save')}
                </Button>
              </CardFooter>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <CardTitle>{t('system.settings.api.egress.auditTitle')}</CardTitle>
                    <CardDescription>{t('system.settings.api.egress.auditDescription')}</CardDescription>
                  </div>
                  <Button variant="outline" size="sm" onClick={fetchEgressAudits} disabled={egressAuditLoading}>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    {t('system.settings.api.egress.refresh')}
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {egressAuditLoading && <div className="text-sm text-muted-foreground">{t('system.settings.api.egress.auditLoading')}</div>}
                {!egressAuditLoading && egressAudits.length === 0 && (
                  <div className="text-sm text-muted-foreground">{t('system.settings.api.egress.auditEmpty')}</div>
                )}
                {egressAudits.length > 0 && (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('system.settings.api.egress.auditColumns.time')}</TableHead>
                        <TableHead>{t('system.settings.api.egress.auditColumns.allow')}</TableHead>
                        <TableHead>{t('system.settings.api.egress.auditColumns.block')}</TableHead>
                        <TableHead>{t('system.settings.api.egress.auditColumns.operator')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {egressAudits.map((audit) => (
                        <TableRow key={audit.id}>
                          <TableCell>{formatTimestamp(audit.created_at)}</TableCell>
                          <TableCell>{audit.allowlist.length}</TableCell>
                          <TableCell>{audit.blocklist.length}</TableCell>
                          <TableCell>{audit.created_by || '-'}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default Page
