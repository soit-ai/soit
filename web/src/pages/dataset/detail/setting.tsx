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
  getDataset,
  updateDataset,
  deleteDataset,
  listIndexes,
  createIndex,
  updateIndex,
  deleteIndex,
  rebuildIndex,
  queryDataset,
  type Index,
  type QueryResponse,
} from '@/services/dataset-service'
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

const visibilityOptions = [
  { value: 'private', labelKey: 'dataset.visibility.private' },
  { value: 'workspace', labelKey: 'dataset.visibility.workspace' },
  { value: 'tenant', labelKey: 'dataset.visibility.tenant' },
]

const metricOptions = [
  { value: 'cosine', label: 'cosine' },
  { value: 'l2', label: 'l2' },
  { value: 'ip', label: 'ip' },
]

const strategyOptions = [
  { value: 'vector', labelKey: 'dataset.query.strategy.vector' },
  { value: 'keyword', labelKey: 'dataset.query.strategy.keyword' },
  { value: 'hybrid', labelKey: 'dataset.query.strategy.hybrid' },
  { value: 'multi_index', labelKey: 'dataset.query.strategy.multiIndex' },
]

function Page() {
  const { datasetId } = useParams<{ datasetId: string }>()
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
    setHeaderContent(<PageHeader title={t('dataset.setting.title')} />)
    return () => setHeaderContent(null)
  }, [setHeaderContent, t])

  useEffect(() => {
    if (!datasetId) return
    const fetchDataset = async () => {
      try {
        setLoading(true)
        const data = await getDataset(datasetId)
        setForm({
          name: data.name || '',
          description: data.description || '',
          visibility: data.visibility || 'private',
        })
      } catch (error) {
        toast.error(t('dataset.setting.toast.fetchError'))
        console.error('Failed to fetch dataset settings:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchDataset()
  }, [datasetId, t])

  useEffect(() => {
    if (!datasetId) return
    const fetchIndexes = async () => {
      try {
        setIndexesLoading(true)
        const data = await listIndexes(datasetId, { limit: 50, offset: 0 })
        setIndexes(data)
      } catch (error) {
        toast.error(t('dataset.setting.indexes.toast.fetchError'))
        console.error('Failed to fetch indexes:', error)
      } finally {
        setIndexesLoading(false)
      }
    }
    fetchIndexes()
  }, [datasetId, t])

  const refreshIndexes = async () => {
    if (!datasetId) return
    try {
      setIndexesLoading(true)
      const data = await listIndexes(datasetId, { limit: 50, offset: 0 })
      setIndexes(data)
    } catch (error) {
      toast.error(t('dataset.setting.indexes.toast.refreshError'))
      console.error('Failed to refresh indexes:', error)
    } finally {
      setIndexesLoading(false)
    }
  }

  const handleSave = async () => {
    if (!datasetId) return
    if (!form.name.trim()) {
      toast.error(t('dataset.setting.toast.nameRequired'))
      return
    }
    try {
      setSaving(true)
      const updated = await updateDataset(datasetId, {
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        visibility: form.visibility,
      })
      setForm({
        name: updated.name || '',
        description: updated.description || '',
        visibility: updated.visibility || 'private',
      })
      toast.success(t('dataset.setting.toast.saveSuccess'))
    } catch (error) {
      toast.error(t('dataset.setting.toast.saveError'))
      console.error('Failed to update dataset:', error)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!datasetId) return
    try {
      setDeleting(true)
      await deleteDataset(datasetId)
      toast.success(t('dataset.setting.toast.deleteSuccess'))
      navigate('/dataset')
    } catch (error) {
      toast.error(t('dataset.setting.toast.deleteError'))
      console.error('Failed to delete dataset:', error)
    } finally {
      setDeleting(false)
    }
  }

  const handleCreateIndex = async () => {
    if (!datasetId) return
    if (!createIndexForm.name.trim() || !createIndexForm.embedding_model_ref.trim()) {
      toast.error(t('dataset.setting.indexes.toast.createRequired'))
      return
    }
    try {
      setCreatingIndex(true)
      await createIndex(datasetId, {
        name: createIndexForm.name.trim(),
        provider: createIndexForm.provider,
        embedding_model_ref: createIndexForm.embedding_model_ref.trim(),
        dimension: createIndexForm.dimension ? Number(createIndexForm.dimension) : undefined,
        metric_type: createIndexForm.metric_type,
        is_primary: createIndexForm.is_primary,
      })
      toast.success(t('dataset.setting.indexes.toast.createSuccess'))
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
      toast.error(t('dataset.setting.indexes.toast.createError'))
      console.error('Failed to create index:', error)
    } finally {
      setCreatingIndex(false)
    }
  }

  const handleSetPrimary = async (indexId: string) => {
    if (!datasetId) return
    try {
      setIndexActionLoading(indexId)
      await updateIndex(datasetId, indexId, { is_primary: true })
      toast.success(t('dataset.setting.indexes.toast.setPrimarySuccess'))
      refreshIndexes()
    } catch (error) {
      toast.error(t('dataset.setting.indexes.toast.setPrimaryError'))
      console.error('Failed to update index:', error)
    } finally {
      setIndexActionLoading(null)
    }
  }

  const handleRebuild = async (indexId: string) => {
    if (!datasetId) return
    try {
      setIndexActionLoading(indexId)
      await rebuildIndex(datasetId, indexId)
      toast.success(t('dataset.setting.indexes.toast.rebuildSuccess'))
      refreshIndexes()
    } catch (error) {
      toast.error(t('dataset.setting.indexes.toast.rebuildError'))
      console.error('Failed to rebuild index:', error)
    } finally {
      setIndexActionLoading(null)
    }
  }

  const handleDeleteIndex = async () => {
    if (!datasetId || !deleteIndexTarget) return
    try {
      setIndexActionLoading(deleteIndexTarget.id)
      await deleteIndex(datasetId, deleteIndexTarget.id)
      toast.success(t('dataset.setting.indexes.toast.deleteSuccess'))
      setDeleteIndexTarget(null)
      refreshIndexes()
    } catch (error) {
      toast.error(t('dataset.setting.indexes.toast.deleteError'))
      console.error('Failed to delete index:', error)
    } finally {
      setIndexActionLoading(null)
    }
  }

  const handleQuery = async () => {
    if (!datasetId) return
    if (!queryText.trim()) {
      toast.error(t('dataset.query.toast.empty'))
      return
    }
    try {
      setQueryLoading(true)
      const data = await queryDataset(datasetId, {
        query: queryText.trim(),
        top_k: queryTopK,
        strategy: queryStrategy as 'vector' | 'keyword' | 'hybrid' | 'multi_index',
        index_id: queryIndexId || undefined,
        use_rerank: queryUseRerank,
      })
      setQueryResult(data)
    } catch (error) {
      toast.error(t('dataset.query.toast.error'))
      console.error('Failed to query dataset:', error)
    } finally {
      setQueryLoading(false)
    }
  }

  const primaryIndex = useMemo(() => indexes.find((item) => item.is_primary), [indexes])
  const citations = queryResult?.citations || []

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="w-full max-w-xl grid grid-cols-3">
          <TabsTrigger value="basic">{t('dataset.setting.tabs.basic')}</TabsTrigger>
          <TabsTrigger value="indexes">{t('dataset.setting.tabs.indexes')}</TabsTrigger>
          <TabsTrigger value="query">{t('dataset.setting.tabs.query')}</TabsTrigger>
        </TabsList>

        <TabsContent value="basic" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{t('dataset.setting.basic.title')}</CardTitle>
              <CardDescription>{t('dataset.setting.basic.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-2">
                <Label htmlFor="dataset-name">{t('dataset.setting.basic.name')}</Label>
                <Input
                  id="dataset-name"
                  value={form.name}
                  onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
                  disabled={loading}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="dataset-desc">{t('dataset.setting.basic.descriptionLabel')}</Label>
                <Textarea
                  id="dataset-desc"
                  value={form.description}
                  onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
                  disabled={loading}
                />
              </div>
              <div className="grid gap-2">
                <Label>{t('dataset.setting.basic.visibility')}</Label>
                <Select
                  value={form.visibility}
                  onValueChange={(value) => setForm((prev) => ({ ...prev, visibility: value }))}
                  disabled={loading}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('dataset.setting.basic.visibilityPlaceholder')} />
                  </SelectTrigger>
                  <SelectContent>
                    {visibilityOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {t(option.labelKey)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button onClick={handleSave} disabled={saving || loading}>
                {saving ? t('dataset.setting.basic.saving') : t('dataset.setting.basic.save')}
              </Button>
            </CardContent>
          </Card>

          <Card className="border-destructive/40">
            <CardHeader>
              <CardTitle className="text-destructive">{t('dataset.setting.danger.title')}</CardTitle>
              <CardDescription>{t('dataset.setting.danger.description')}</CardDescription>
            </CardHeader>
            <CardContent>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="destructive" disabled={deleting || loading}>
                    {deleting ? t('dataset.setting.danger.deleting') : t('dataset.setting.danger.delete')}
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>{t('dataset.setting.danger.confirmTitle')}</AlertDialogTitle>
                    <AlertDialogDescription>
                      {t('dataset.setting.danger.confirmDescription')}
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>{t('dataset.setting.danger.cancel')}</AlertDialogCancel>
                    <AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground">
                      {t('dataset.setting.danger.confirm')}
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
                <CardTitle>{t('dataset.setting.indexes.title')}</CardTitle>
                <CardDescription>{t('dataset.setting.indexes.description')}</CardDescription>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={refreshIndexes} disabled={indexesLoading}>
                  {indexesLoading ? t('dataset.setting.indexes.refreshing') : t('dataset.setting.indexes.refresh')}
                </Button>
                <Button onClick={() => setCreateIndexOpen(true)}>{t('dataset.setting.indexes.create')}</Button>
              </div>
            </CardHeader>
            <CardContent>
              {indexesLoading && <div className="text-sm text-muted-foreground">{t('dataset.setting.indexes.loading')}</div>}
              {!indexesLoading && indexes.length === 0 && (
                <div className="text-sm text-muted-foreground">{t('dataset.setting.indexes.empty')}</div>
              )}
              {!indexesLoading && indexes.length > 0 && (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('dataset.setting.indexes.columns.name')}</TableHead>
                      <TableHead>{t('dataset.setting.indexes.columns.model')}</TableHead>
                      <TableHead>{t('dataset.setting.indexes.columns.status')}</TableHead>
                      <TableHead>{t('dataset.setting.indexes.columns.vectorCount')}</TableHead>
                      <TableHead>{t('dataset.setting.indexes.columns.primary')}</TableHead>
                      <TableHead>{t('dataset.setting.indexes.columns.actions')}</TableHead>
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
                        <TableCell>{item.vector_count}</TableCell>
                        <TableCell>{item.is_primary ? t('dataset.setting.indexes.primaryYes') : t('dataset.setting.indexes.primaryNo')}</TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-2">
                            {!item.is_primary && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleSetPrimary(item.id)}
                                disabled={indexActionLoading === item.id}
                              >
                                {t('dataset.setting.indexes.actions.setPrimary')}
                              </Button>
                            )}
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleRebuild(item.id)}
                              disabled={indexActionLoading === item.id}
                            >
                              {t('dataset.setting.indexes.actions.rebuild')}
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => setDeleteIndexTarget(item)}
                              disabled={indexActionLoading === item.id}
                            >
                              {t('dataset.setting.indexes.actions.delete')}
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
              <CardTitle>{t('dataset.query.title')}</CardTitle>
              <CardDescription>{t('dataset.query.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-2">
                <Label htmlFor="query-text">{t('dataset.query.textLabel')}</Label>
                <Textarea
                  id="query-text"
                  value={queryText}
                  onChange={(e) => setQueryText(e.target.value)}
                  placeholder={t('dataset.query.textPlaceholder')}
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="grid gap-2">
                  <Label>{t('dataset.query.strategyLabel')}</Label>
                  <Select value={queryStrategy} onValueChange={setQueryStrategy}>
                    <SelectTrigger>
                      <SelectValue placeholder={t('dataset.query.strategyPlaceholder')} />
                    </SelectTrigger>
                    <SelectContent>
                      {strategyOptions.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {t(option.labelKey)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label>{t('dataset.query.topKLabel')}</Label>
                  <Input
                    type="number"
                    min={1}
                    max={100}
                    value={queryTopK}
                    onChange={(e) => setQueryTopK(Number(e.target.value || 1))}
                  />
                </div>
                <div className="grid gap-2">
                  <Label>{t('dataset.query.indexLabel')}</Label>
                  <Select value={queryIndexId} onValueChange={setQueryIndexId}>
                    <SelectTrigger>
                      <SelectValue placeholder={primaryIndex ? primaryIndex.name : t('dataset.query.indexPlaceholder')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">{t('dataset.query.indexDefault')}</SelectItem>
                      {indexes.map((item) => (
                        <SelectItem key={item.id} value={item.id}>
                          {item.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label>{t('dataset.query.rerankLabel')}</Label>
                  <div className="flex items-center gap-2">
                    <Switch checked={queryUseRerank} onCheckedChange={setQueryUseRerank} />
                    <span className="text-sm text-muted-foreground">
                      {queryUseRerank ? t('dataset.query.rerankEnabled') : t('dataset.query.rerankDisabled')}
                    </span>
                  </div>
                </div>
              </div>
              <Button onClick={handleQuery} disabled={queryLoading}>
                {queryLoading ? t('dataset.query.running') : t('dataset.query.run')}
              </Button>
            </CardContent>
          </Card>

          {queryResult && (
            <Card>
              <CardHeader>
                <CardTitle>{t('dataset.query.resultsTitle')}</CardTitle>
                <CardDescription>{t('dataset.query.resultsCount', { total: queryResult.total })}</CardDescription>
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
                        {t('dataset.query.snippetsLabel')} {result.snippets.join(' / ')}
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
                <CardTitle>{t('dataset.query.citationsTitle')}</CardTitle>
                <CardDescription>{t('dataset.query.citationsCount', { total: citations.length })}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {citations.length === 0 && (
                  <div className="text-sm text-muted-foreground">{t('dataset.query.citationsEmpty')}</div>
                )}
                {citations.map((citation) => (
                  <div key={`${citation.chunk_id}-${citation.rank}`} className="rounded-md border p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">#{citation.rank}</span>
                      <span className="text-xs text-muted-foreground">
                        {t('dataset.query.citationsScore', { score: citation.score.toFixed(4) })}
                      </span>
                    </div>
                    <div className="text-sm font-medium">
                      {citation.title || citation.doc_key || citation.document_id}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {t('dataset.query.citationsChunk', { chunk: citation.chunk_no ?? '-' })}{' '}
                      {t('dataset.query.citationsPage', { page: citation.page_no ?? '-' })}
                    </div>
                    {citation.source_uri && (
                      <div className="text-xs text-muted-foreground break-all">
                        {t('dataset.query.citationsSource', { source: citation.source_uri })}
                      </div>
                    )}
                    {citation.section_path && citation.section_path.length > 0 && (
                      <div className="text-xs text-muted-foreground">
                        {t('dataset.query.citationsSection', { section: citation.section_path.join(' / ') })}
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
            <DialogTitle>{t('dataset.setting.indexes.createDialog.title')}</DialogTitle>
            <DialogDescription>{t('dataset.setting.indexes.createDialog.description')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="index-name">{t('dataset.setting.indexes.createDialog.name')}</Label>
              <Input
                id="index-name"
                value={createIndexForm.name}
                onChange={(e) => setCreateIndexForm((prev) => ({ ...prev, name: e.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="index-model">{t('dataset.setting.indexes.createDialog.model')}</Label>
              <Input
                id="index-model"
                value={createIndexForm.embedding_model_ref}
                onChange={(e) => setCreateIndexForm((prev) => ({ ...prev, embedding_model_ref: e.target.value }))}
                placeholder={t('dataset.setting.indexes.createDialog.modelPlaceholder')}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="index-dim">{t('dataset.setting.indexes.createDialog.dimension')}</Label>
              <Input
                id="index-dim"
                type="number"
                value={createIndexForm.dimension}
                onChange={(e) => setCreateIndexForm((prev) => ({ ...prev, dimension: e.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label>{t('dataset.setting.indexes.createDialog.metric')}</Label>
              <Select
                value={createIndexForm.metric_type}
                onValueChange={(value) => setCreateIndexForm((prev) => ({ ...prev, metric_type: value }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder={t('dataset.setting.indexes.createDialog.metricPlaceholder')} />
                </SelectTrigger>
                <SelectContent>
                  {metricOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center justify-between rounded-md border p-3">
              <div>
                <div className="text-sm font-medium">{t('dataset.setting.indexes.createDialog.primaryTitle')}</div>
                <div className="text-xs text-muted-foreground">{t('dataset.setting.indexes.createDialog.primaryDescription')}</div>
              </div>
              <Switch
                checked={createIndexForm.is_primary}
                onCheckedChange={(checked) => setCreateIndexForm((prev) => ({ ...prev, is_primary: checked }))}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateIndexOpen(false)}>
              {t('dataset.setting.indexes.createDialog.cancel')}
            </Button>
            <Button onClick={handleCreateIndex} disabled={creatingIndex}>
              {creatingIndex ? t('dataset.setting.indexes.createDialog.submitting') : t('dataset.setting.indexes.createDialog.submit')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteIndexTarget} onOpenChange={(open) => !open && setDeleteIndexTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('dataset.setting.indexes.deleteDialog.title')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('dataset.setting.indexes.deleteDialog.description')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('dataset.setting.indexes.deleteDialog.cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteIndex}
              className="bg-destructive text-destructive-foreground"
              disabled={!!deleteIndexTarget && indexActionLoading === deleteIndexTarget.id}
            >
              {t('dataset.setting.indexes.deleteDialog.confirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

export default Page
