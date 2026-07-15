import { useTranslation } from '@/i18n'
import { useState, useMemo, useEffect, useCallback } from 'react'
import { Item } from './ui/item'
import { Search, SlidersHorizontal, Plus, Star, Tag, TrendingUp, Clock } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useNavLayout } from '@/components/layout/nav-layout'
import { listProviders } from '@/services/provider-service'
import { useDrawer } from '@/hooks/use-drawer'
import { ProviderList } from './setting/ui/provider-list'

function ModelHeader({ onAddProvider }: { onAddProvider: () => void }) {
  const { t } = useTranslation()

  return (
    <div className="flex flex-1 justify-between">
      <div className="flex flex-col">
        <h2 className="text-lg font-bold tracking-tight">{t('model.home.title')}</h2>
        <p className="text-sm text-muted-foreground mt-1">{t('model.home.description')}</p>
      </div>
      <div className="flex items-center gap-2">
        <Button className="gap-2" size={'sm'} onClick={onAddProvider}>
          <Plus className="h-4 w-4" />
          {t('model.home.add')}
        </Button>
      </div>
    </div>
  )
}

function BoxPage() {
  const [list, setList] = useState<any[]>([])
  const { t } = useTranslation()
  const [searchQuery, setSearchQuery] = useState('')
  const [activeCategory, setActiveCategory] = useState('all')
  const [sortBy, setSortBy] = useState('default')
  const [counts, setCounts] = useState({ all: 0, llm: 0, embedding: 0, tts: 0 })
  const { setHeaderContent } = useNavLayout()
  const drawer = useDrawer()

  const loadProviders = useCallback(async () => {
    try {
      const providers = await listProviders()
      const items = providers.map((provider) => ({
        id: provider.id,
        name: provider.name,
        icon: provider.kind,
        iconText: provider.kind,
        tags: ['LLM'],
        desc: provider.baseUrl || provider.kind,
        kind: provider.kind,
        baseUrl: provider.baseUrl,
        credentialRef: provider.credentialRef,
        status: provider.status,
        syncPolicy: provider.syncPolicy,
      }))
      setList(items)
    } catch (error) {
      console.error('Failed to load providers:', error)
      setList([])
    }
  }, [])

  const handleOpenProviders = useCallback(() => {
    drawer.open(
      <ProviderList
        open={true}
        onOpenChange={() => {}}
        onSaveProvider={() => loadProviders()}
        onDeleteProvider={() => loadProviders()}
      />,
      {
        direction: 'right',
        contentClassName: '!w-[680px] !max-w-[680px] h-full',
        onClose: () => loadProviders(),
      }
    )
  }, [drawer, loadProviders])

  // Set header content.
  useEffect(() => {
    setHeaderContent(<ModelHeader onAddProvider={handleOpenProviders} />)
    return () => setHeaderContent(null)
  }, [setHeaderContent, handleOpenProviders])

  useEffect(() => {
    loadProviders()
  }, [loadProviders])

  const filteredList = useMemo(() => {
    let result = [...list]
    if (searchQuery) {
      result = result.filter(item =>
        item.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.desc?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }
    // Simulate category filtering.
    if (activeCategory !== 'all') {
      if (activeCategory === 'llm') {
        result = result.filter(item => item.tags?.includes('LLM'))
      } else if (activeCategory === 'embedding') {
        result = result.filter(item => item.tags?.includes('TEXT EMBEDDING'))
      } else if (activeCategory === 'tts') {
        result = result.filter(item => item.tags?.includes('TTS'))
      }
    }
    // Sort results.
    if (sortBy === 'name') {
      result.sort((a, b) => a.name.localeCompare(b.name))
    } else if (sortBy === 'popular') {
      result.sort((a, b) => (b.hot ? 1 : 0) - (a.hot ? 1 : 0))
    }
    return result
  }, [searchQuery, activeCategory, sortBy])
  
  // Calculate counts per category.
  useEffect(() => {
    const allCount = list.length
    const llmCount = list.filter(item => item.tags?.includes('LLM')).length
    const embeddingCount = list.filter(item => item.tags?.includes('TEXT EMBEDDING')).length
    const ttsCount = list.filter(item => item.tags?.includes('TTS')).length
    
    setCounts({
      all: allCount,
      llm: llmCount,
      embedding: embeddingCount,
      tts: ttsCount
    })
  }, [list])

  return (
    <div className="flex flex-1 flex-col gap-4 p-4 md:p-6">
      {/* Category tabs and search/sort controls. */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-4">
        <Tabs defaultValue="all" value={activeCategory} onValueChange={setActiveCategory}>
          <TabsList>
            <TabsTrigger value="all" className="flex items-center">
              <Tag className="mr-2 h-4 w-4" />
              {t('model.home.tabs.all')}
              <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs">
                {counts.all}
              </span>
            </TabsTrigger>
            <TabsTrigger value="llm" className="flex items-center">
              <Tag className="mr-2 h-4 w-4" />
              {t('model.home.tabs.llm')}
              <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs">
                {counts.llm}
              </span>
            </TabsTrigger>
            <TabsTrigger value="embedding" className="flex items-center">
              <Tag className="mr-2 h-4 w-4" />
              {t('model.home.tabs.embedding')}
              <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs">
                {counts.embedding}
              </span>
            </TabsTrigger>
            <TabsTrigger value="tts" className="flex items-center">
              <Tag className="mr-2 h-4 w-4" />
              {t('model.home.tabs.tts')}
              <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs">
                {counts.tts}
              </span>
            </TabsTrigger>
          </TabsList>
        </Tabs>
        
        <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
          <div className="relative w-full sm:w-[200px]">
            <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder={t('model.home.searchPlaceholder')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8"
            />
          </div>
          <Select value={sortBy} onValueChange={setSortBy}>
            <SelectTrigger className="w-full sm:w-[140px]">
              <SlidersHorizontal className="mr-2 h-4 w-4" />
              <SelectValue placeholder={t('model.home.sort.placeholder')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="default">
                <div className="flex items-center">
                  <Tag className="mr-2 h-4 w-4" />
                  {t('model.home.sort.default')}
                </div>
              </SelectItem>
              <SelectItem value="name">
                <div className="flex items-center">
                  <Tag className="mr-2 h-4 w-4" />
                  {t('model.home.sort.name')}
                </div>
              </SelectItem>
              <SelectItem value="popular">
                <div className="flex items-center">
                  <TrendingUp className="mr-2 h-4 w-4" />
                  {t('model.home.sort.popular')}
                </div>
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid-box">
        {filteredList.map((item, index) => (
          <Item key={index} item={item} index={index} />
        ))}
      </div>
    </div>
  )
}

export default BoxPage
