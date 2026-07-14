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
import { Key, Plus, Copy, RefreshCw, Eye, EyeOff, AlertTriangle, ShieldCheck } from 'lucide-react'
import { toast } from '@/hooks/use-toast'
import {
  createApiKey,
  listApiKeys,
  revokeApiKey,
  rotateApiKey,
  type ApiKeyItem,
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
  const [apiKeys, setApiKeys] = useState<ApiKeyItem[]>([])
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [showKey, setShowKey] = useState<Record<string, boolean>>({})
  const [revealedKeys, setRevealedKeys] = useState<Record<string, string>>({})
  const [newKeyName, setNewKeyName] = useState('')
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
        title: '错误',
        description: '获取 API 密钥失败',
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
        title: '错误',
        description: '获取用量限制失败',
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
        title: '错误',
        description: '获取出口策略失败',
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
        title: '错误',
        description: '获取出口策略审计失败',
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
      title: '复制成功',
      description: 'API 密钥已复制到剪贴板',
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
        title: '错误',
        description: '请输入密钥名称',
        type: 'error',
      })
      return
    }
    try {
      setActionLoading('create')
      const result = await createApiKey({ name: newKeyName })
      setApiKeys(prev => [result.item, ...prev])
      setRevealedKeys(prev => ({ ...prev, [result.item.id]: result.api_key }))
      setNewKeyName('')
      toast({
        title: '创建成功',
        description: 'API 密钥已创建，请立即保存',
      })
    } catch (error) {
      toast({
        title: '错误',
        description: '创建 API 密钥失败',
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
        title: '撤销成功',
        description: 'API 密钥已撤销',
      })
    } catch (error) {
      toast({
        title: '错误',
        description: '撤销 API 密钥失败',
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
        title: '轮换成功',
        description: '新密钥已生成，请立即保存',
      })
    } catch (error) {
      toast({
        title: '错误',
        description: '轮换 API 密钥失败',
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
        title: '保存成功',
        description: '用量限制已更新',
      })
    } catch (error) {
      toast({
        title: '错误',
        description: '保存用量限制失败',
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
        title: '保存成功',
        description: '工作区出口策略已更新',
      })
    } catch (error) {
      toast({
        title: '错误',
        description: '保存出口策略失败',
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
        <h3 className="text-lg font-bold tracking-tight">API 管理</h3>
        <p className="text-sm text-muted-foreground mt-1">管理您的 API 密钥与用量限制</p>
      </div>

      <Tabs defaultValue="keys" className="w-full">
        <TabsList className="mb-4 grid w-full max-w-xl grid-cols-3">
          <TabsTrigger value="keys">API 密钥</TabsTrigger>
          <TabsTrigger value="limits">用量限制</TabsTrigger>
          <TabsTrigger value="egress">出口策略</TabsTrigger>
        </TabsList>

        <TabsContent value="keys">
          <Card>
            <CardHeader>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <CardTitle>API 密钥</CardTitle>
                  <CardDescription>创建、轮换和撤销 API 访问密钥</CardDescription>
                </div>
                <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
                  <Input
                    value={newKeyName}
                    onChange={(e) => setNewKeyName(e.target.value)}
                    placeholder="新密钥名称"
                    className="w-full sm:w-48"
                  />
                  <Button onClick={handleCreateKey} disabled={actionLoading === 'create'}>
                    <Plus className="mr-2 h-4 w-4" />
                    创建密钥
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {loading && <div className="text-sm text-muted-foreground">加载中...</div>}
              {!loading && sortedKeys.length === 0 && (
                <div className="text-sm text-muted-foreground">暂无 API 密钥</div>
              )}
              <div className="space-y-4">
                {sortedKeys.map((apiKey) => {
                  const rawKey = revealedKeys[apiKey.id]
                  const displayValue = rawKey || `${apiKey.key_prefix}...`
                  const isVisible = showKey[apiKey.id] && rawKey
                  const statusLabel = apiKey.status === 'active' ? '活跃' : '已撤销'
                  return (
                    <div key={apiKey.id} className="flex flex-col space-y-2 rounded-md border p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <Key className="h-5 w-5 text-muted-foreground" />
                          <span className="font-medium">{apiKey.name}</span>
                          <Badge variant={apiKey.status === 'active' ? 'default' : 'destructive'}>
                            {statusLabel}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-2">
                          {rawKey && (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => toggleShowKey(apiKey.id)}
                              title={isVisible ? '隐藏密钥' : '显示密钥'}
                            >
                              {isVisible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleCopyKey(rawKey || displayValue)}
                            title="复制密钥"
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
                                轮换
                              </Button>
                              <Button
                                variant="destructive"
                                size="sm"
                                onClick={() => handleRevokeKey(apiKey.id)}
                                disabled={actionLoading === apiKey.id}
                              >
                                撤销
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
                        <span>创建于: {apiKey.created_at}</span>
                        <span>最后使用: {apiKey.last_used_at || '-'}</span>
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
              <CardTitle>用量限制</CardTitle>
              <CardDescription>配置当前工作区的速率限制与配额</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>注意</AlertTitle>
                <AlertDescription>
                  限制为空表示使用默认值或不限制。更改限制可能影响工作区运行。
                </AlertDescription>
              </Alert>

              <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="llm-rate-limit">LLM 每分钟请求数</Label>
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
                  <Label htmlFor="tool-rate-limit">工具每分钟请求数</Label>
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
                  <Label htmlFor="llm-daily-quota">LLM 每日配额</Label>
                  <Input
                    id="llm-daily-quota"
                    type="number"
                    value={policyForm.llm_daily_quota}
                    onChange={(e) => setPolicyForm(prev => ({ ...prev, llm_daily_quota: e.target.value }))}
                    min="0"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="tool-daily-quota">工具每日配额</Label>
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
                保存配置
              </Button>
            </CardFooter>
          </Card>
        </TabsContent>

        <TabsContent value="egress">
          <div className="grid gap-4 xl:grid-cols-[1fr_0.95fr]">
            <Card>
              <CardHeader>
                <CardTitle>工作区出口策略</CardTitle>
                <CardDescription>配置工具和运行时外部 HTTP 调用允许访问的域名与显式阻断域名</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <Alert>
                  <ShieldCheck className="h-4 w-4" />
                  <AlertTitle>运行时生效</AlertTitle>
                  <AlertDescription>
                    外部 URL 会先匹配阻断列表，再匹配工作区、租户和全局允许列表。支持通配符，例如 *.example.com。
                  </AlertDescription>
                </Alert>

                <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="egress-allowlist">允许域名</Label>
                    <Textarea
                      id="egress-allowlist"
                      value={egressForm.allowlist}
                      onChange={(e) => setEgressForm(prev => ({ ...prev, allowlist: e.target.value }))}
                      placeholder={'api.example.com\n*.trusted.internal'}
                      className="min-h-40 font-mono text-sm"
                    />
                    <p className="text-xs text-muted-foreground">每行一个域名，也可以用逗号分隔。</p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="egress-blocklist">阻断域名</Label>
                    <Textarea
                      id="egress-blocklist"
                      value={egressForm.blocklist}
                      onChange={(e) => setEgressForm(prev => ({ ...prev, blocklist: e.target.value }))}
                      placeholder={'*.blocked.example\n169.254.169.254'}
                      className="min-h-40 font-mono text-sm"
                    />
                    <p className="text-xs text-muted-foreground">阻断列表优先于所有允许列表。</p>
                  </div>
                </div>
              </CardContent>
              <CardFooter className="flex justify-end">
                <Button onClick={handleSaveEgressPolicy} disabled={egressLoading}>
                  保存出口策略
                </Button>
              </CardFooter>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <CardTitle>策略审计</CardTitle>
                    <CardDescription>最近的工作区出口策略变更记录</CardDescription>
                  </div>
                  <Button variant="outline" size="sm" onClick={fetchEgressAudits} disabled={egressAuditLoading}>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    刷新
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {egressAuditLoading && <div className="text-sm text-muted-foreground">加载中...</div>}
                {!egressAuditLoading && egressAudits.length === 0 && (
                  <div className="text-sm text-muted-foreground">暂无策略变更记录</div>
                )}
                {egressAudits.length > 0 && (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>时间</TableHead>
                        <TableHead>允许</TableHead>
                        <TableHead>阻断</TableHead>
                        <TableHead>操作者</TableHead>
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
