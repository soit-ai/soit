import { useTranslation } from '@/i18n'
import { useState, useMemo, useEffect } from 'react'
import { Item } from './ui/item'
import { BotMessageSquare, Search, SlidersHorizontal, Plus, Star, Tag, TrendingUp, Clock } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useNavLayout } from '@/components/layout/nav-layout'

const _list = [
  {
    id: 1,
    title: 'GPT-Researcher EN',
    icon: <BotMessageSquare color="blue" />,
    iconType: 'icon',
    desc: 'GPT-Reasearcher is an expert in internet topic research. It can efficiently decompose a topic into sub-questions and provide a professional research report from a comprehensive perspective.',
    tags: ['AI', 'Research', 'NLP'],
    hot: true,
  },
  { id: 2, title: 'Azure', icon: '😊', iconType: 'emoji' },
  { id: 2, title: 'Deepseek', icon: '🤖', iconType: 'emoji' },
  { id: 3, title: 'Google', icon: '🥁', iconType: 'emoji' },
  { id: 3, title: 'Grok', icon: 'https://registry.npmmirror.com/@lobehub/icons-static-png/latest/files/dark/google-brand-color.png', iconType: 'image' },
]

function WorkflowHeader() {
  const { t } = useTranslation()
  return (
    <div className="flex flex-1 justify-between">
      <div className="flex flex-col">
        <h2 className="text-lg font-bold tracking-tight">{t('workflow.list.header.title')}</h2>
        <p className="text-sm text-muted-foreground mt-1">{t('workflow.list.header.subtitle')}</p>
      </div>
      <div className="flex items-center gap-2">
        <Button className="gap-2" size={'sm'}>
          <Plus className="h-4 w-4" />
          {t('workflow.list.header.create')}
        </Button>
      </div>
    </div>
  )
}

function BoxPage() {
  const { t } = useTranslation()
  const [searchQuery, setSearchQuery] = useState('')
  const [activeCategory, setActiveCategory] = useState('all')
  const [sortBy, setSortBy] = useState('default')
  const [counts, setCounts] = useState({ all: 0, recent: 0, favorite: 0, created: 0 })
  const { setHeaderContent } = useNavLayout()

  useEffect(() => {
    setHeaderContent(<WorkflowHeader />)
    return () => setHeaderContent(null)
  }, [setHeaderContent])

  const filteredList = useMemo(() => {
    let result = [..._list]
    if (searchQuery) {
      result = result.filter(item =>
        item.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.desc?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }
    if (activeCategory !== 'all') {
      if (activeCategory === 'recent') {
        result = result.slice(0, Math.floor(result.length * 0.6))
      } else if (activeCategory === 'favorite') {
        result = result.filter((_, index) => index % 3 === 0)
      } else if (activeCategory === 'created') {
        result = result.filter((_, index) => index % 5 !== 0)
      }
    }
    if (sortBy === 'name') {
      result.sort((a, b) => a.title.localeCompare(b.title))
    } else if (sortBy === 'popular') {
      result.sort((a, b) => (b.hot ? 1 : 0) - (a.hot ? 1 : 0))
    }
    return result
  }, [searchQuery, activeCategory, sortBy])
  
  useEffect(() => {
    const allCount = _list.length
    const recentCount = Math.floor(_list.length * 0.6)
    const favoriteCount = _list.filter((_, index) => index % 3 === 0).length
    const createdCount = _list.filter((_, index) => index % 5 !== 0).length
    
    setCounts({
      all: allCount,
      recent: recentCount,
      favorite: favoriteCount,
      created: createdCount
    })
  }, [_list])

  return (
    <div className="flex flex-1 flex-col gap-4 p-4 md:p-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-4">
        <Tabs defaultValue="all" value={activeCategory} onValueChange={setActiveCategory}>
          <TabsList>
            <TabsTrigger value="all" className="flex items-center">
              <Tag className="mr-2 h-4 w-4" />
              {t('workflow.list.tabs.all')}
              <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs">
                {counts.all}
              </span>
            </TabsTrigger>
            <TabsTrigger value="recent" className="flex items-center">
              <Clock className="mr-2 h-4 w-4" />
              {t('workflow.list.tabs.recent')}
              <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs">
                {counts.recent}
              </span>
            </TabsTrigger>
            <TabsTrigger value="favorite" className="flex items-center">
              <Star className="mr-2 h-4 w-4" />
              {t('workflow.list.tabs.favorite')}
              <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs">
                {counts.favorite}
              </span>
            </TabsTrigger>
            <TabsTrigger value="created" className="flex items-center">
              <Plus className="mr-2 h-4 w-4" />
              {t('workflow.list.tabs.created')}
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
              placeholder={t('workflow.list.searchPlaceholder')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8"
            />
          </div>
          <Select value={sortBy} onValueChange={setSortBy}>
            <SelectTrigger className="w-full sm:w-[140px]">
              <SlidersHorizontal className="mr-2 h-4 w-4" />
              <SelectValue placeholder={t('workflow.list.sort.placeholder')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="default">
                <div className="flex items-center">
                  <Tag className="mr-2 h-4 w-4" />
                  {t('workflow.list.sort.default')}
                </div>
              </SelectItem>
              <SelectItem value="name">
                <div className="flex items-center">
                  <Tag className="mr-2 h-4 w-4" />
                  {t('workflow.list.sort.name')}
                </div>
              </SelectItem>
              <SelectItem value="popular">
                <div className="flex items-center">
                  <TrendingUp className="mr-2 h-4 w-4" />
                  {t('workflow.list.sort.popular')}
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
