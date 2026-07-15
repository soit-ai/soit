import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from '@/i18n'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useParams } from 'react-router'
import { toast } from 'sonner'
import { useNavLayout } from '@/components/layout/nav-layout'
import { PageHeader } from './ui/setting/page-header'
import {
  createKnowledgeIndex,
  deleteKnowledgeBase,
  deleteKnowledgeIndex,
  getKnowledgeBase,
  listKnowledgeIndexes,
  queryKnowledge,
  rebuildKnowledgeIndex,
  updateKnowledgeBase,
  updateKnowledgeIndex,
  type KnowledgeIndex as Index,
  type KnowledgeQueryResponse as QueryResponse,
} from '@/services/knowledge-service'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Switch } from '@/components/ui/switch'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { useNavigate } from '@/hooks/use-navigate'
import type { TranslationKey } from '@/i18n/types'

const visibilityOptions = [
  { value: 'private', labelKey: 'knowledge.visibility.private' },
  { value: 'workspace', labelKey: 'knowledge.visibility.workspace' },
  { value: 'tenant', labelKey: 'knowledge.visibility.tenant' },
]

const metricOptions = [
  { value: 'cosine', labelKey: 'knowledge.query.metric.cosine' },
  { value: 'l2', labelKey: 'knowledge.query.metric.l2' },
  { value: 'ip', labelKey: 'knowledge.query.metric.ip' },
]

const strategyOptions = [
  { value: 'vector', labelKey: 'knowledge.query.strategy.vector' },
  { value: 'keyword', labelKey: 'knowledge.query.strategy.keyword' },
  { value: 'hybrid', labelKey: 'knowledge.query.strategy.hybrid' },
  { value: 'multi_index', labelKey: 'knowledge.query.strategy.multiIndex' },
]

const DEFAULT_QUERY_INDEX_VALUE = '__default__'

function Page() {
  const { knowledgeId } = useParams<{ knowledgeId: string }>()
  const { t } = useTranslation()
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [activeTab, setActiveTab] = useState('basic')
  const [form, setForm] = useState({
    name: '',
    description: '',
    visibility: 'private',
  })

  const [indexes, setIndexes] = useState<Index[]>([])
  const [indexesLoading, setIndexesLoading] = useState(false)
  const [createIndexOpen, setCreateIndexOpen] = useState(false)
  const [creatingIndex, setCreatingIndex] = useState(false)
  const [indexActionLoading, setIndexActionLoading] = useState<string | null>(null)
  const [deleteIndexTarget, setDeleteIndexTarget] = useState<Index | null>(null)
  const [createIndexForm, setCreateIndexForm] = useState({
    name: '',
    provider: 'milvus',
    embedding_model_ref: '',
    dimension: '',
    metric_type: 'cosine',
    is_primary: true,
  })

  const [queryText, setQueryText] = useState('')
  const [queryTopK, setQueryTopK] = useState(5)
  const [queryStrategy, setQueryStrategy] = useState('vector')
  const [queryIndexId, setQueryIndexId] = useState<string>('')
  const [queryUseRerank, setQueryUseRerank] = useState(false)
  const [queryLoading, setQueryLoading] = useState(false)
  const [queryResult, setQueryResult] = useState<QueryResponse | null>(null)

  const { setHeaderContent } = useNavLayout()
  const navigate = useNavigate()

  useEffect(() => {
    setHeaderContent(<PageHeader title={t('knowledge.setting.title')} />)
    return () => setHeaderContent(null)
  }, [setHeaderContent, t])

  useEffect(() => {
    if (!knowledgeId) return
    const fetchKnowledge = async () => {
      try {
        setLoading(true)
        const data = await getKnowledgeBase(knowledgeId)
        setForm({
          name: data.name || '',
          description: data.description || '',
          visibility: data.visibility || 'private',
        })
      } catch (error) {
        toast.error(t('knowledge.setting.toast.fetchError'))
        console.error('Failed to fetch knowledge settings:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchKnowledge()
  }, [knowledgeId, t])

  useEffect(() => {
    if (!knowledgeId) return
    const fetchIndexes = async () => {
      try {
        setIndexesLoading(true)
        const data = await listKnowledgeIndexes(knowledgeId, { limit: 50, offset: 0 })
        setIndexes(data)
      } catch (error) {
        toast.error(t('knowledge.setting.indexes.toast.fetchError'))
        console.error('Failed to fetch indexes:', error)
      } finally {
        setIndexesLoading(false)
      }
    }
    fetchIndexes()
  }, [knowledgeId, t])

  const refreshIndexes = async () => {
    if (!knowledgeId) return
    try {
      setIndexesLoading(true)
      const data = await listKnowledgeIndexes(knowledgeId, { limit: 50, offset: 0 })
      setIndexes(data)
    } catch (error) {
      toast.error(t('knowledge.setting.indexes.toast.refreshError'))
      console.error('Failed to refresh indexes:', error)
    } finally {
      setIndexesLoading(false)
    }
  }

  const handleSave = async () => {
    if (!knowledgeId) return
    if (!form.name.trim()) {
      toast.error(t('knowledge.setting.toast.nameRequired'))
      return
    }
    try {
      setSaving(true)
      const updated = await updateKnowledgeBase(knowledgeId, {
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        visibility: form.visibility,
      })
      setForm({
        name: updated.name || '',
        description: updated.description || '',
        visibility: updated.visibility || 'private',
      })
      toast.success(t('knowledge.setting.toast.saveSuccess'))
    } catch (error) {
      toast.error(t('knowledge.setting.toast.saveError'))
      console.error('Failed to update knowledge:', error)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!knowledgeId) return
    try {
      setDeleting(true)
      await deleteKnowledgeBase(knowledgeId)
      toast.success(t('knowledge.setting.toast.deleteSuccess'))
      navigate('/knowledge')
    } catch (error) {
      toast.error(t('knowledge.setting.toast.deleteError'))
      console.error('Failed to delete knowledge:', error)
    } finally {
      setDeleting(false)
    }
  }

  const handleCreateIndex = async () => {
    if (!knowledgeId) return
    if (!createIndexForm.name.trim() || !createIndexForm.embedding_model_ref.trim()) {
      toast.error(t('knowledge.setting.indexes.toast.createRequired'))
      return
    }
    try {
      setCreatingIndex(true)
      await createKnowledgeIndex(knowledgeId, {
        name: createIndexForm.name.trim(),
        provider: createIndexForm.provider,
        embedding_model_ref: createIndexForm.embedding_model_ref.trim(),
        dimension: createIndexForm.dimension ? Number(createIndexForm.dimension) : undefined,
        metric_type: createIndexForm.metric_type,
        is_primary: createIndexForm.is_primary,
      })
      toast.success(t('knowledge.setting.indexes.toast.createSuccess'))
      setCreateIndexOpen(false)
      setCreateIndexForm({
        name: '',
        provider: 'milvus',
        embedding_model_ref: '',
        dimension: '',
        metric_type: 'cosine',
        is_primary: true,
      })
      refreshIndexes()
    } catch (error) {
      toast.error(t('knowledge.setting.indexes.toast.createError'))
      console.error('Failed to create index:', error)
    } finally {
      setCreatingIndex(false)
    }
  }

  const handleSetPrimary = async (indexId: string) => {
    if (!knowledgeId) return
    try {
      setIndexActionLoading(indexId)
      await updateKnowledgeIndex(knowledgeId, indexId, { is_primary: true })
      toast.success(t('knowledge.setting.indexes.toast.setPrimarySuccess'))
      refreshIndexes()
    } catch (error) {
      toast.error(t('knowledge.setting.indexes.toast.setPrimaryError'))
      console.error('Failed to update index:', error)
    } finally {
      setIndexActionLoading(null)
    }
  }

  const handleRebuild = async (indexId: string) => {
    if (!knowledgeId) return
    try {
      setIndexActionLoading(indexId)
      await rebuildKnowledgeIndex(knowledgeId, indexId)
      toast.success(t('knowledge.setting.indexes.toast.rebuildSuccess'))
      refreshIndexes()
    } catch (error) {
      toast.error(t('knowledge.setting.indexes.toast.rebuildError'))
      console.error('Failed to rebuild index:', error)
    } finally {
      setIndexActionLoading(null)
    }
  }

  const handleDeleteIndex = async () => {
    if (!knowledgeId || !deleteIndexTarget) return
    try {
      setIndexActionLoading(deleteIndexTarget.id)
      await deleteKnowledgeIndex(knowledgeId, deleteIndexTarget.id)
      toast.success(t('knowledge.setting.indexes.toast.deleteSuccess'))
      setDeleteIndexTarget(null)
      refreshIndexes()
    } catch (error) {
      toast.error(t('knowledge.setting.indexes.toast.deleteError'))
      console.error('Failed to delete index:', error)
    } finally {
      setIndexActionLoading(null)
    }
  }

  const handleQuery = async () => {
    if (!knowledgeId) return
    if (!queryText.trim()) {
      toast.error(t('knowledge.query.toast.empty'))
      return
    }
    try {
      setQueryLoading(true)
      const data = await queryKnowledge(knowledgeId, {
        query: queryText.trim(),
        top_k: queryTopK,
        strategy: queryStrategy as 'vector' | 'keyword' | 'hybrid' | 'multi_index',
        index_id: queryIndexId && queryIndexId !== DEFAULT_QUERY_INDEX_VALUE ? queryIndexId : undefined,
        use_rerank: queryUseRerank,
      })
      setQueryResult(data)
    } catch (error) {
      toast.error(t('knowledge.query.toast.error'))
      console.error('Failed to query knowledge base:', error)
    } finally {
      setQueryLoading(false)
    }
  }

  const primaryIndex = useMemo(() => indexes.find((item) => item.is_primary), [indexes])
  const citations = queryResult?.citations || []
  const formatDateTime = (value?: string | null) => {
    if (!value) return '-'
    return new Date(value).toLocaleString()
  }

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="w-full max-w-xl grid grid-cols-3">
          <TabsTrigger value="basic">{t('knowledge.setting.tabs.basic')}</TabsTrigger>
          <TabsTrigger value="indexes">{t('knowledge.setting.tabs.indexes')}</TabsTrigger>
          <TabsTrigger value="query">{t('knowledge.setting.tabs.query')}</TabsTrigger>
        </TabsList>

        <TabsContent value="basic" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{t('knowledge.setting.basic.title')}</CardTitle>
              <CardDescription>{t('knowledge.setting.basic.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-2">
                <Label htmlFor="knowledge-name">{t('knowledge.setting.basic.name')}</Label>
                <Input
                  id="knowledge-name"
                  value={form.name}
                  onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
                  disabled={loading}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="knowledge-desc">{t('knowledge.setting.basic.descriptionLabel')}</Label>
                <Textarea
                  id="knowledge-desc"
                  value={form.description}
                  onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
                  disabled={loading}
                />
              </div>
              <div className="grid gap-2">
                <Label>{t('knowledge.setting.basic.visibility')}</Label>
                <Select
                  value={form.visibility}
                  onValueChange={(value) => setForm((prev) => ({ ...prev, visibility: value }))}
                  disabled={loading}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('knowledge.setting.basic.visibilityPlaceholder')} />
                  </SelectTrigger>
                  <SelectContent>
                    {visibilityOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {t(option.labelKey as TranslationKey)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button onClick={handleSave} disabled={saving || loading}>
                {saving ? t('knowledge.setting.basic.saving') : t('knowledge.setting.basic.save')}
              </Button>
            </CardContent>
          </Card>

          <Card className="border-destructive/40">
            <CardHeader>
              <CardTitle className="text-destructive">{t('knowledge.setting.danger.title')}</CardTitle>
              <CardDescription>{t('knowledge.setting.danger.description')}</CardDescription>
            </CardHeader>
            <CardContent>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="destructive" disabled={deleting || loading}>
                    {deleting ? t('knowledge.setting.danger.deleting') : t('knowledge.setting.danger.delete')}
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>{t('knowledge.setting.danger.confirmTitle')}</AlertDialogTitle>
                    <AlertDialogDescription>
                      {t('knowledge.setting.danger.confirmDescription')}
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>{t('knowledge.setting.danger.cancel')}</AlertDialogCancel>
                    <AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground">
                      {t('knowledge.setting.danger.confirm')}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="indexes" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>{t('knowledge.setting.indexes.title')}</CardTitle>
                <CardDescription>{t('knowledge.setting.indexes.description')}</CardDescription>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={refreshIndexes} disabled={indexesLoading}>
                  {indexesLoading ? t('knowledge.setting.indexes.refreshing') : t('knowledge.setting.indexes.refresh')}
                </Button>
                <Button onClick={() => setCreateIndexOpen(true)}>{t('knowledge.setting.indexes.create')}</Button>
              </div>
            </CardHeader>
            <CardContent>
              {indexesLoading && <div className="text-sm text-muted-foreground">{t('knowledge.setting.indexes.loading')}</div>}
              {!indexesLoading && indexes.length === 0 && (
                <div className="text-sm text-muted-foreground">{t('knowledge.setting.indexes.empty')}</div>
              )}
              {!indexesLoading && indexes.length > 0 && (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('knowledge.setting.indexes.columns.name')}</TableHead>
                      <TableHead>{t('knowledge.setting.indexes.columns.model')}</TableHead>
                      <TableHead>{t('knowledge.setting.indexes.columns.status')}</TableHead>
                      <TableHead>{t('knowledge.setting.indexes.columns.build')}</TableHead>
                      <TableHead>{t('knowledge.setting.indexes.columns.vectorCount')}</TableHead>
                      <TableHead>{t('knowledge.setting.indexes.columns.lastError')}</TableHead>
                      <TableHead>{t('knowledge.setting.indexes.columns.lastRun')}</TableHead>
                      <TableHead>{t('knowledge.setting.indexes.columns.primary')}</TableHead>
                      <TableHead>{t('knowledge.setting.indexes.columns.actions')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {indexes.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell className="font-medium">{item.name}</TableCell>
                        <TableCell>{item.embedding_model_ref}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{item.status}</Badge>
                        </TableCell>
                        <TableCell>
                          <div className="text-sm">
                            v{item.build_version}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {formatDateTime(item.last_build_at)}
                          </div>
                        </TableCell>
                        <TableCell>{item.vector_count}</TableCell>
                        <TableCell className="max-w-[220px]">
                          {item.last_error_message || item.last_error_code ? (
                            <div className="space-y-1">
                              {item.last_error_code && <Badge variant="destructive">{item.last_error_code}</Badge>}
                              {item.last_error_message && (
                                <div className="text-xs text-muted-foreground line-clamp-2">
                                  {item.last_error_message}
                                </div>
                              )}
                            </div>
                          ) : (
                            <span className="text-xs text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {item.last_run_id ? (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => navigate(`/observe/runs/${item.last_run_id}`)}
                            >
                              {t('knowledge.setting.indexes.actions.viewRun')}
                            </Button>
                          ) : (
                            <span className="text-xs text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell>{item.is_primary ? t('knowledge.setting.indexes.primaryYes') : t('knowledge.setting.indexes.primaryNo')}</TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-2">
                            {!item.is_primary && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleSetPrimary(item.id)}
                                disabled={indexActionLoading === item.id}
                              >
                                {t('knowledge.setting.indexes.actions.setPrimary')}
                              </Button>
                            )}
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleRebuild(item.id)}
                              disabled={indexActionLoading === item.id}
                            >
                              {t('knowledge.setting.indexes.actions.rebuild')}
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => setDeleteIndexTarget(item)}
                              disabled={indexActionLoading === item.id}
                            >
                              {t('knowledge.setting.indexes.actions.delete')}
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="query" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{t('knowledge.query.title')}</CardTitle>
              <CardDescription>{t('knowledge.query.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-2">
                <Label htmlFor="query-text">{t('knowledge.query.textLabel')}</Label>
                <Textarea
                  id="query-text"
                  value={queryText}
                  onChange={(e) => setQueryText(e.target.value)}
                  placeholder={t('knowledge.query.textPlaceholder')}
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="grid gap-2">
                  <Label>{t('knowledge.query.strategyLabel')}</Label>
                  <Select value={queryStrategy} onValueChange={setQueryStrategy}>
                    <SelectTrigger>
                      <SelectValue placeholder={t('knowledge.query.strategyPlaceholder')} />
                    </SelectTrigger>
                    <SelectContent>
                      {strategyOptions.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {t(option.labelKey as TranslationKey)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label>{t('knowledge.query.topKLabel')}</Label>
                  <Input
                    type="number"
                    min={1}
                    max={100}
                    value={queryTopK}
                    onChange={(e) => setQueryTopK(Number(e.target.value || 1))}
                  />
                </div>
                <div className="grid gap-2">
                  <Label>{t('knowledge.query.indexLabel')}</Label>
                  <Select value={queryIndexId || DEFAULT_QUERY_INDEX_VALUE} onValueChange={setQueryIndexId}>
                    <SelectTrigger>
                      <SelectValue placeholder={primaryIndex ? primaryIndex.name : t('knowledge.query.indexPlaceholder')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={DEFAULT_QUERY_INDEX_VALUE}>{t('knowledge.query.indexDefault')}</SelectItem>
                      {indexes.map((item) => (
                        <SelectItem key={item.id} value={item.id}>
                          {item.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label>{t('knowledge.query.rerankLabel')}</Label>
                  <div className="flex items-center gap-2">
                    <Switch checked={queryUseRerank} onCheckedChange={setQueryUseRerank} />
                    <span className="text-sm text-muted-foreground">
                      {queryUseRerank ? t('knowledge.query.rerankEnabled') : t('knowledge.query.rerankDisabled')}
                    </span>
                  </div>
                </div>
              </div>
              <Button onClick={handleQuery} disabled={queryLoading}>
                {queryLoading ? t('knowledge.query.running') : t('knowledge.query.run')}
              </Button>
            </CardContent>
          </Card>

          {queryResult && (
            <Card>
              <CardHeader>
                <CardTitle>{t('knowledge.query.resultsTitle')}</CardTitle>
                <CardDescription>{t('knowledge.query.resultsCount', { total: queryResult.total })}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {queryResult.results.map((result, index) => (
                  <div key={`${result.chunk_id}-${index}`} className="space-y-2 border-b pb-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">#{index + 1}</span>
                      <span className="text-xs text-muted-foreground">score {result.score.toFixed(4)}</span>
                    </div>
                    <div className="text-sm whitespace-pre-wrap text-muted-foreground">
                      {result.text}
                    </div>
                    {result.snippets?.length > 0 && (
                      <div className="text-xs text-muted-foreground">
                        {t('knowledge.query.snippetsLabel')} {result.snippets.join(' / ')}
                      </div>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {queryResult && (
            <Card>
              <CardHeader>
                <CardTitle>{t('knowledge.query.citationsTitle')}</CardTitle>
                <CardDescription>{t('knowledge.query.citationsCount', { total: citations.length })}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {citations.length === 0 && (
                  <div className="text-sm text-muted-foreground">{t('knowledge.query.citationsEmpty')}</div>
                )}
                {citations.map((citation) => (
                  <div key={`${citation.chunk_id}-${citation.rank}`} className="rounded-md border p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">#{citation.rank}</span>
                      <span className="text-xs text-muted-foreground">
                        {t('knowledge.query.citationsScore', { score: citation.score.toFixed(4) })}
                      </span>
                    </div>
                    <div className="text-sm font-medium">
                      {citation.title || citation.doc_key || citation.document_id}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {t('knowledge.query.citationsChunk', { chunk: citation.chunk_no ?? '-' })}{' '}
                      {t('knowledge.query.citationsPage', { page: citation.page_no ?? '-' })}
                    </div>
                    {citation.source_uri && (
                      <div className="text-xs text-muted-foreground break-all">
                        {t('knowledge.query.citationsSource', { source: citation.source_uri })}
                      </div>
                    )}
                    {citation.section_path && citation.section_path.length > 0 && (
                      <div className="text-xs text-muted-foreground">
                        {t('knowledge.query.citationsSection', { section: citation.section_path.join(' / ') })}
                      </div>
                    )}
                    {citation.snippet && (
                      <div className="text-sm text-muted-foreground whitespace-pre-wrap">
                        {citation.snippet}
                      </div>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      <Dialog open={createIndexOpen} onOpenChange={setCreateIndexOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{t('knowledge.setting.indexes.createDialog.title')}</DialogTitle>
            <DialogDescription>{t('knowledge.setting.indexes.createDialog.description')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="index-name">{t('knowledge.setting.indexes.createDialog.name')}</Label>
              <Input
                id="index-name"
                value={createIndexForm.name}
                onChange={(e) => setCreateIndexForm((prev) => ({ ...prev, name: e.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="index-model">{t('knowledge.setting.indexes.createDialog.model')}</Label>
              <Input
                id="index-model"
                value={createIndexForm.embedding_model_ref}
                onChange={(e) => setCreateIndexForm((prev) => ({ ...prev, embedding_model_ref: e.target.value }))}
                placeholder={t('knowledge.setting.indexes.createDialog.modelPlaceholder')}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="index-dim">{t('knowledge.setting.indexes.createDialog.dimension')}</Label>
              <Input
                id="index-dim"
                type="number"
                value={createIndexForm.dimension}
                onChange={(e) => setCreateIndexForm((prev) => ({ ...prev, dimension: e.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label>{t('knowledge.setting.indexes.createDialog.metric')}</Label>
              <Select
                value={createIndexForm.metric_type}
                onValueChange={(value) => setCreateIndexForm((prev) => ({ ...prev, metric_type: value }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder={t('knowledge.setting.indexes.createDialog.metricPlaceholder')} />
                </SelectTrigger>
                <SelectContent>
                  {metricOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {t(option.labelKey as TranslationKey)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center justify-between rounded-md border p-3">
              <div>
                <div className="text-sm font-medium">{t('knowledge.setting.indexes.createDialog.primaryTitle')}</div>
                <div className="text-xs text-muted-foreground">{t('knowledge.setting.indexes.createDialog.primaryDescription')}</div>
              </div>
              <Switch
                checked={createIndexForm.is_primary}
                onCheckedChange={(checked) => setCreateIndexForm((prev) => ({ ...prev, is_primary: checked }))}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateIndexOpen(false)}>
              {t('knowledge.setting.indexes.createDialog.cancel')}
            </Button>
            <Button onClick={handleCreateIndex} disabled={creatingIndex}>
              {creatingIndex ? t('knowledge.setting.indexes.createDialog.submitting') : t('knowledge.setting.indexes.createDialog.submit')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteIndexTarget} onOpenChange={(open) => !open && setDeleteIndexTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('knowledge.setting.indexes.deleteDialog.title')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('knowledge.setting.indexes.deleteDialog.description')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('knowledge.setting.indexes.deleteDialog.cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteIndex}
              className="bg-destructive text-destructive-foreground"
              disabled={!!deleteIndexTarget && indexActionLoading === deleteIndexTarget.id}
            >
              {t('knowledge.setting.indexes.deleteDialog.confirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

export default Page
