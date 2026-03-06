import { useState, useMemo, useEffect } from 'react'
import { useTranslation } from '@/i18n'
import { Item } from './ui/item'
import { Database, Search, SlidersHorizontal, Plus, Star, Tag, Clock, RefreshCw } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useNavLayout } from '@/components/layout/nav-layout'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { toast } from 'sonner'
import { createDataset, listDatasets, type Dataset } from '@/services/dataset-service'

const PAGE_SIZE = 24
const RECENT_DAYS = 7

const datasetTypes = [
  { value: 'document', labelKey: 'dataset.type.document' },
  { value: 'qa', labelKey: 'dataset.type.qa' },
  { value: 'code', labelKey: 'dataset.type.code' },
  { value: 'graph', labelKey: 'dataset.type.graph' },
  { value: 'other', labelKey: 'dataset.type.other' },
]

const visibilityOptions = [
  { value: 'private', labelKey: 'dataset.visibility.private' },
  { value: 'workspace', labelKey: 'dataset.visibility.workspace' },
  { value: 'tenant', labelKey: 'dataset.visibility.tenant' },
]

const isRecentDataset = (dataset: Dataset) => {
  if (!dataset.updated_at) return false
  const updatedAt = new Date(dataset.updated_at).getTime()
  if (Number.isNaN(updatedAt)) return false
  const now = Date.now()
  return now - updatedAt <= RECENT_DAYS * 24 * 60 * 60 * 1000
}

const isFavoriteDataset = (dataset: Dataset) => {
  const tags = dataset.tags || []
  return tags.includes('favorite') || tags.includes('star')
}

function DatasetHeader({
  onCreate,
  onRefresh,
  isRefreshing,
}: {
  onCreate: () => void
  onRefresh: () => void
  isRefreshing: boolean
}) {
  const { t } = useTranslation()

  return (
    <div className="flex flex-1 justify-between">
      <div className="flex flex-col">
        <h2 className="text-lg font-bold tracking-tight">{t('dataset.list.title')}</h2>
        <p className="text-sm text-muted-foreground mt-1">{t('dataset.list.description')}</p>
      </div>
      <div className="flex items-center gap-2">
        <Button className="gap-2" size={'sm'} onClick={onCreate}>
          <Plus className="h-4 w-4" />
          {t('dataset.list.create')}
        </Button>
        <Button className="gap-2" size={'sm'} variant="outline" onClick={onRefresh} disabled={isRefreshing}>
          <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
        </Button>
      </div>
    </div>
  )
}

function BoxPage() {
  const { t } = useTranslation()
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [activeCategory, setActiveCategory] = useState('all')
  const [sortBy, setSortBy] = useState('default')
  const [nextPageToken, setNextPageToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createForm, setCreateForm] = useState({
    name: '',
    type: 'document',
    description: '',
    visibility: 'private',
  })
  const { setHeaderContent } = useNavLayout()

  const fetchDatasets = async ({ append = false }: { append?: boolean } = {}) => {
    if (append && !nextPageToken) return
    try {
      if (append) {
        setLoadingMore(true)
      } else {
        setLoading(true)
      }
      const response = await listDatasets({
        page_size: PAGE_SIZE,
        page_token: append ? nextPageToken || undefined : undefined,
      })
      const items = response.items || []
      setDatasets((prev) => (append ? [...prev, ...items] : items))
      setNextPageToken(response.next_page_token || null)
    } catch (error) {
      toast.error(t('dataset.list.toast.fetchError'))
      console.error('Failed to fetch datasets:', error)
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }

  useEffect(() => {
    fetchDatasets({ append: false })
  }, [])

  useEffect(() => {
    setHeaderContent(
      <DatasetHeader
        onCreate={() => setCreateOpen(true)}
        onRefresh={() => fetchDatasets({ append: false })}
        isRefreshing={loading}
      />
    )
    return () => setHeaderContent(null)
  }, [setHeaderContent, loading])

  const counts = useMemo(() => {
    const allCount = datasets.length
    const recentCount = datasets.filter(isRecentDataset).length
    const favoriteCount = datasets.filter(isFavoriteDataset).length
    const createdCount = datasets.length
    return {
      all: allCount,
      recent: recentCount,
      favorite: favoriteCount,
      created: createdCount,
    }
  }, [datasets])

  const filteredList = useMemo(() => {
    let result = [...datasets]
    if (searchQuery) {
      result = result.filter((item) =>
        item.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.description?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }
    if (activeCategory !== 'all') {
      if (activeCategory === 'recent') {
        result = result.filter(isRecentDataset)
      } else if (activeCategory === 'favorite') {
        result = result.filter(isFavoriteDataset)
      }
    }
    if (sortBy === 'name') {
      result.sort((a, b) => a.name.localeCompare(b.name))
    } else if (sortBy === 'newest') {
      result.sort((a, b) => {
        const aTime = new Date(a.updated_at).getTime() || 0
        const bTime = new Date(b.updated_at).getTime() || 0
        return bTime - aTime
      })
    }
    return result
  }, [datasets, searchQuery, activeCategory, sortBy])

  const handleCreateDataset = async () => {
    const trimmedName = createForm.name.trim()
    if (!trimmedName) {
      toast.error(t('dataset.list.toast.nameRequired'))
      return
    }
    try {
      setCreating(true)
      await createDataset({
        name: trimmedName,
        type: createForm.type,
        description: createForm.description?.trim() || undefined,
        visibility: createForm.visibility,
      })
      toast.success(t('dataset.list.toast.createSuccess'))
      setCreateOpen(false)
      setCreateForm({
        name: '',
        type: 'document',
        description: '',
        visibility: 'private',
      })
      fetchDatasets({ append: false })
    } catch (error) {
      toast.error(t('dataset.list.toast.createError'))
      console.error('Failed to create dataset:', error)
    } finally {
      setCreating(false)
    }
  }

  const mappedItems = filteredList.map((dataset) => ({
    id: dataset.id,
    title: dataset.name,
    subtitle: t('dataset.list.card.subtitle', {
      docCount: dataset.doc_count,
      chunkCount: dataset.chunk_count,
    }),
    icon: <Database className="h-5 w-5 text-primary" />,
    iconType: 'icon',
    desc: dataset.description || '',
    tags: dataset.tags || [],
  }))

  return (
    <div className="flex flex-1 flex-col gap-4 p-4 md:p-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-4">
        <Tabs defaultValue="all" value={activeCategory} onValueChange={setActiveCategory}>
          <TabsList>
            <TabsTrigger value="all" className="flex items-center">
              <Tag className="mr-2 h-4 w-4" />
              {t('dataset.list.categories.all')}
              <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs">
                {counts.all}
              </span>
            </TabsTrigger>
            <TabsTrigger value="recent" className="flex items-center">
              <Clock className="mr-2 h-4 w-4" />
              {t('dataset.list.categories.recent')}
              <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs">
                {counts.recent}
              </span>
            </TabsTrigger>
            <TabsTrigger value="favorite" className="flex items-center">
              <Star className="mr-2 h-4 w-4" />
              {t('dataset.list.categories.favorite')}
              <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs">
                {counts.favorite}
              </span>
            </TabsTrigger>
            <TabsTrigger value="created" className="flex items-center">
              <Plus className="mr-2 h-4 w-4" />
              {t('dataset.list.categories.created')}
              <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs">
                {counts.created}
              </span>
            </TabsTrigger>
          </TabsList>
        </Tabs>

        <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
          <div className="relative w-full sm:w-[200px]">
            <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder={t('dataset.list.searchPlaceholder')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8"
            />
          </div>
          <Select value={sortBy} onValueChange={setSortBy}>
            <SelectTrigger className="w-full sm:w-[140px]">
              <SlidersHorizontal className="mr-2 h-4 w-4" />
              <SelectValue placeholder={t('dataset.list.sort.placeholder')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="default">
                <div className="flex items-center">
                  <Tag className="mr-2 h-4 w-4" />
                  {t('dataset.list.sort.default')}
                </div>
              </SelectItem>
              <SelectItem value="name">
                <div className="flex items-center">
                  <Tag className="mr-2 h-4 w-4" />
                  {t('dataset.list.sort.name')}
                </div>
              </SelectItem>
              <SelectItem value="newest">
                <div className="flex items-center">
                  <Clock className="mr-2 h-4 w-4" />
                  {t('dataset.list.sort.newest')}
                </div>
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {loading && (
        <div className="text-sm text-muted-foreground">{t('dataset.list.loading')}</div>
      )}

      {!loading && mappedItems.length === 0 && (
        <div className="text-sm text-muted-foreground">{t('dataset.list.empty')}</div>
      )}

      <div className="grid-box">
        {mappedItems.map((item, index) => (
          <Item key={item.id || index} item={item} index={index} />
        ))}
      </div>

      {nextPageToken && (
        <div className="flex justify-center">
          <Button variant="outline" onClick={() => fetchDatasets({ append: true })} disabled={loadingMore}>
            {loadingMore ? t('dataset.list.loadingMore') : t('dataset.list.loadMore')}
          </Button>
        </div>
      )}

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{t('dataset.list.dialog.title')}</DialogTitle>
            <DialogDescription>{t('dataset.list.dialog.description')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="dataset-name">{t('dataset.list.form.name')}</Label>
              <Input
                id="dataset-name"
                value={createForm.name}
                onChange={(e) => setCreateForm((prev) => ({ ...prev, name: e.target.value }))}
                placeholder={t('dataset.list.form.namePlaceholder')}
              />
            </div>
            <div className="space-y-2">
              <Label>{t('dataset.list.form.type')}</Label>
              <Select
                value={createForm.type}
                onValueChange={(value) => setCreateForm((prev) => ({ ...prev, type: value }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder={t('dataset.list.form.typePlaceholder')} />
                </SelectTrigger>
                <SelectContent>
                  {datasetTypes.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {t(option.labelKey)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>{t('dataset.list.form.visibility')}</Label>
              <Select
                value={createForm.visibility}
                onValueChange={(value) => setCreateForm((prev) => ({ ...prev, visibility: value }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder={t('dataset.list.form.visibilityPlaceholder')} />
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
            <div className="space-y-2">
              <Label htmlFor="dataset-desc">{t('dataset.list.form.description')}</Label>
              <Textarea
                id="dataset-desc"
                value={createForm.description}
                onChange={(e) => setCreateForm((prev) => ({ ...prev, description: e.target.value }))}
                placeholder={t('dataset.list.form.descriptionPlaceholder')}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              {t('dataset.list.dialog.cancel')}
            </Button>
            <Button onClick={handleCreateDataset} disabled={creating || !createForm.name.trim()}>
              {creating ? t('dataset.list.dialog.submitting') : t('dataset.list.dialog.submit')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default BoxPage
