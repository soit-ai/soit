import { useTranslation } from '@/i18n'
import { useState, useEffect, useMemo } from 'react'
import { Item } from './ui/item'
import { getAppid } from '@/utils'
import { BotMessageSquare, Search, SlidersHorizontal, Plus, Star, Tag, TrendingUp, Clock, RefreshCwIcon } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Checkbox } from '@/components/ui/checkbox'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useNavLayout } from '@/components/layout/nav-layout'

const _list = [
  {
    id: getAppid(),
    title: 'GPT-Researcher EN',
    icon: <BotMessageSquare color="blue" />,
    iconType: 'icon',
    desc: 'GPT-Reasearcher is an expert in internet topic research. It can efficiently decompose a topic into sub-questions and provide a professional research report from a comprehensive perspective.',
    tags: ['AI', 'Research', 'NLP'],
    hot: true,
  },
  { id: getAppid(), title: 'Azure', icon: '😊', iconType: 'emoji' },
  { id: getAppid(), title: 'Deepseek', icon: '🤖', iconType: 'emoji' },
  { id: getAppid(), title: 'Google', icon: '🥁', iconType: 'emoji' },
  {
    id: getAppid(),
    title: 'GPT-Researcher EN',
    icon: <BotMessageSquare color="blue" />,
    iconType: 'icon',
    desc: 'GPT-Reasearcher is an expert in internet topic research. It can efficiently decompose a topic into sub-questions and provide a professional research report from a comprehensive perspective.',
    tags: ['AI', 'Research', 'NLP'],
  },
  { id: getAppid(), title: 'Azure', icon: '😊', iconType: 'emoji' },
  { id: getAppid(), title: 'Deepseek', icon: '🤖', iconType: 'emoji' },
  { id: getAppid(), title: 'Google', icon: '🥁', iconType: 'emoji' },
  {
    id: getAppid(),
    title: 'GPT-Researcher EN',
    icon: <BotMessageSquare color="blue" />,
    iconType: 'icon',
    desc: 'GPT-Reasearcher is an expert in internet topic research. It can efficiently decompose a topic into sub-questions and provide a professional research report from a comprehensive perspective.',
    tags: ['AI', 'Research', 'NLP'],
  },
  { id: getAppid(), title: 'Azure', icon: '😊', iconType: 'emoji' },
  { id: getAppid(), title: 'Deepseek', icon: '🤖', iconType: 'emoji' },
  { id: getAppid(), title: 'Google', icon: '🥁', iconType: 'emoji' },
  {
    id: getAppid(),
    title: 'GPT-Researcher EN',
    icon: <BotMessageSquare color="blue" />,
    iconType: 'icon',
    desc: 'GPT-Reasearcher is an expert in internet topic research. It can efficiently decompose a topic into sub-questions and provide a professional research report from a comprehensive perspective.',
    tags: ['AI', 'Research', 'NLP'],
  },
  { id: getAppid(), title: 'Azure', icon: '😊', iconType: 'emoji' },
  { id: getAppid(), title: 'Deepseek', icon: '🤖', iconType: 'emoji' },
  { id: getAppid(), title: 'Google', icon: '🥁', iconType: 'emoji' },
  { id: getAppid(), title: 'Grok', icon: 'https://registry.npmmirror.com/@lobehub/icons-static-png/latest/files/dark/google-brand-color.png', iconType: 'image' },
]
const categories = [
  { id: 'all', nameKey: 'bot.list.tabs.all', icon: <Tag className="mr-2 h-4 w-4" /> },
  { id: 'recent', nameKey: 'bot.list.tabs.recent', icon: <Clock className="mr-2 h-4 w-4" /> },
  { id: 'favorite', nameKey: 'bot.list.tabs.favorite', icon: <Star className="mr-2 h-4 w-4" /> },
  { id: 'created', nameKey: 'bot.list.tabs.created', icon: <Plus className="mr-2 h-4 w-4" /> },
]

const sortOptions = [
  { id: 'popular', nameKey: 'bot.list.sort.popular', icon: <TrendingUp className="mr-2 h-4 w-4" /> },
  { id: 'newest', nameKey: 'bot.list.sort.newest', icon: <Clock className="mr-2 h-4 w-4" /> },
  { id: 'name', nameKey: 'bot.list.sort.name', icon: <Tag className="mr-2 h-4 w-4" /> },
]

const tagOptions = ['AI', 'Research', 'NLP', 'Coding', 'Writing', 'Translation', 'Data']

function BoxHeader() {
  const { t } = useTranslation()
  return (
    <div className="flex flex-1 justify-between">
      <div className="flex flex-col">
        <h3 className="text-lg font-bold tracking-tight">{t('bot.list.header.title')}</h3>
        <p className="text-sm text-muted-foreground mt-1">{t('bot.list.header.subtitle')}</p>
      </div>
      <div className="flex items-center gap-2">
        <Button className="gap-2" size={'sm'}>
          <Plus className="h-4 w-4" />
          {t('bot.list.header.create')}
        </Button>
        <Button className="gap-2" size={'sm'} variant={'outline'}>
          <RefreshCwIcon className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}

function BoxPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [activeCategory, setActiveCategory] = useState('all')
  const [sortBy, setSortBy] = useState('popular')
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const { t } = useTranslation()
  const { setHeaderContent } = useNavLayout()

  useEffect(() => {
    setHeaderContent(<BoxHeader />)
    return () => setHeaderContent(null)
  }, [setHeaderContent])

  useEffect(() => {
    setIsLoading(true)
    const timer = setTimeout(() => {
      setIsLoading(false)
    }, 500)
    return () => clearTimeout(timer)
  }, [activeCategory, sortBy, selectedTags])

  const filteredList = useMemo(() => {
    let result = [..._list]

    if (searchQuery) {
      result = result.filter((item) => item.title?.toLowerCase().includes(searchQuery.toLowerCase()) || item.desc?.toLowerCase().includes(searchQuery.toLowerCase()))
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

    if (selectedTags.length > 0) {
      result = result.filter((item) => item.tags && selectedTags.some((tag) => item.tags.includes(tag)))
    }

    if (sortBy === 'popular') {
      result.sort((a, b) => (b.hot ? 1 : 0) - (a.hot ? 1 : 0))
    } else if (sortBy === 'newest') {
      result.reverse()
    } else if (sortBy === 'name') {
      result.sort((a, b) => a.title.localeCompare(b.title))
    }

    return result
  }, [searchQuery, activeCategory, sortBy, selectedTags])

  const handleTagToggle = (tag: string) => {
    setSelectedTags((prev) => (prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]))
  }

  return (
    <div className="flex flex-1 flex-col gap-4 p-4 md:p-6">
      <Tabs defaultValue="all" value={activeCategory} onValueChange={setActiveCategory} className="w-full">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-4">
          <TabsList className="w-full md:w-auto grid grid-cols-4 md:flex">
            {categories.map((category) => (
              <TabsTrigger key={category.id} value={category.id} className="flex items-center gap-1">
                {category.icon}
                <span>{t(category.nameKey)}</span>
                {category.id === 'all' && (
                  <Badge variant="secondary" className="ml-1 rounded-full px-1.5 py-0 text-xs">
                    {_list.length}
                  </Badge>
                )}
                {category.id === 'recent' && (
                  <Badge variant="secondary" className="ml-1 rounded-full px-1.5 py-0 text-xs">
                    {Math.floor(_list.length * 0.6)}
                  </Badge>
                )}
                {category.id === 'favorite' && (
                  <Badge variant="secondary" className="ml-1 rounded-full px-1.5 py-0 text-xs">
                    {Math.floor(_list.length * 0.3)}
                  </Badge>
                )}
                {category.id === 'created' && (
                  <Badge variant="secondary" className="ml-1 rounded-full px-1.5 py-0 text-xs">
                    {Math.floor(_list.length * 0.8)}
                  </Badge>
                )}
              </TabsTrigger>
            ))}
          </TabsList>

          <div className="flex items-center gap-2 w-full md:w-auto">
            <div className="relative flex-1 md:w-48">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                type="search"
                placeholder={t('bot.list.searchPlaceholder')}
                className="w-full pl-9"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            <Select value={sortBy} onValueChange={setSortBy}>
              <SelectTrigger className="w-[130px]">
                <SelectValue placeholder={t('bot.list.sort.placeholder')} />
              </SelectTrigger>
              <SelectContent>
                {sortOptions.map((option) => (
                  <SelectItem key={option.id} value={option.id}>
                    <div className="flex items-center">
                      {option.icon}
                      {t(option.nameKey)}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" size="icon" className="h-10 w-10">
                  <SlidersHorizontal className="h-4 w-4" />
                  {selectedTags.length > 0 && (
                    <Badge variant="secondary" className="absolute -top-1 -right-1 w-5 h-5 flex items-center justify-center p-0 text-xs">
                      {selectedTags.length}
                    </Badge>
                  )}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-[200px] p-3">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h4 className="font-medium text-sm">{t('bot.list.filter.title')}</h4>
                    {selectedTags.length > 0 && (
                      <Button variant="ghost" size="sm" className="h-6 px-2 text-xs" onClick={() => setSelectedTags([])}>
                        {t('bot.list.filter.clear')}
                      </Button>
                    )}
                  </div>
                  <ScrollArea className="h-[200px] pr-3">
                    <div className="space-y-2">
                      {tagOptions.map((tag) => (
                        <div key={tag} className="flex items-center space-x-2">
                          <Checkbox id={`tag-${tag}`} checked={selectedTags.includes(tag)} onCheckedChange={() => handleTagToggle(tag)} />
                          <label htmlFor={`tag-${tag}`} className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                            {tag}
                          </label>
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                </div>
              </PopoverContent>
            </Popover>
          </div>
        </div>

        <TabsContent value={activeCategory} className="mt-0">
          {isLoading ? (
            <div className="grid-box animate-pulse">
              {Array(8)
                .fill(0)
                .map((_, index) => (
                  <div key={index} className="bg-muted rounded-lg h-[200px]"></div>
                ))}
            </div>
          ) : filteredList.length > 0 ? (
            <div className="grid-box">
              {filteredList.map((item, index) => (
                <Item key={item.id} item={item} index={index} />
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="rounded-full bg-muted p-3">
                <Search className="h-6 w-6 text-muted-foreground" />
              </div>
              <h3 className="mt-4 text-lg font-semibold">{t('bot.list.empty.title')}</h3>
              <p className="mt-2 text-sm text-muted-foreground max-w-md">{t('bot.list.empty.description')}</p>
              <Button
                variant="outline"
                className="mt-4"
                onClick={() => {
                  setSearchQuery('')
                  setActiveCategory('all')
                  setSortBy('popular')
                  setSelectedTags([])
                }}
              >
                {t('bot.list.empty.clear')}
              </Button>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default BoxPage
