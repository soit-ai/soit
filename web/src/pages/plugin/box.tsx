import { useTranslation } from '@/i18n'
import { useState, useMemo, useEffect, useCallback } from 'react'
import { Item } from './ui/item'
import { Search, SlidersHorizontal, Plus, Tag, TrendingUp, Puzzle } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useNavLayout } from '@/components/layout/nav-layout'
import { RefreshCwIcon } from 'lucide-react'
import { Switch } from '@/components/ui/switch'
import { toast } from 'sonner'
import {
  listPlugins,
  installPlugin,
  uninstallPlugin,
  setPluginEnabled,
  reloadPluginRuntime,
  type Plugin,
} from '@/services/plugin-service'

const resolveTags = (plugin: Plugin) => {
  const tags = plugin.metadata_json?.tags
  if (Array.isArray(tags)) {
    return tags.map((tag) => String(tag))
  }
  return []
}

const resolveIcon = (plugin: Plugin) => {
  const icon = plugin.metadata_json?.icon
  if (typeof icon === 'string' && icon.trim()) {
    return icon
  }
  return <Puzzle className="text-primary" />
}

const resolveIconType = (plugin: Plugin) => {
  const icon = plugin.metadata_json?.icon
  if (typeof icon === 'string' && icon.trim()) {
    return icon.startsWith('http') ? 'image' : 'emoji'
  }
  return 'icon'
}

function PluginHeader({
  onReload,
  loading,
}: {
  onReload: () => void
  loading: boolean
}) {
  const { t } = useTranslation()

  return (
    <div className="flex flex-1 justify-between">
      <div className="flex flex-col">
        <h2 className="text-lg font-bold tracking-tight">{t('plugin.marketplacePage.title')}</h2>
        <p className="text-sm text-muted-foreground mt-1">{t('plugin.marketplacePage.description')}</p>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" className="gap-2" onClick={onReload} disabled={loading}>
          <RefreshCwIcon className="h-4 w-4" />
          {t('plugin.marketplacePage.actions.reload')}
        </Button>
        <Button className="gap-2" size={'sm'}>
          <Plus className="h-4 w-4" />
          {t('plugin.marketplacePage.addPlugin')}
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
  const [plugins, setPlugins] = useState<Plugin[]>([])
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [reloadLoading, setReloadLoading] = useState(false)
  const { setHeaderContent } = useNavLayout()

  const fetchPlugins = useCallback(async () => {
    try {
      setLoading(true)
      const data = await listPlugins({ page_size: 100 })
      setPlugins(data.items || [])
    } catch (error) {
      toast.error(t('plugin.marketplacePage.toast.fetchError'))
      console.error('Failed to fetch plugins:', error)
    } finally {
      setLoading(false)
    }
  }, [t])

  const handleReloadRuntime = useCallback(async () => {
    try {
      setReloadLoading(true)
      const result = await reloadPluginRuntime()
      toast.success(
        t('plugin.marketplacePage.toast.reloadSuccess', { count: result.loaded_count })
      )
      await fetchPlugins()
    } catch (error) {
      toast.error(t('plugin.marketplacePage.toast.reloadError'))
      console.error('Failed to reload runtime:', error)
    } finally {
      setReloadLoading(false)
    }
  }, [fetchPlugins, t])

  // Set header content.
  useEffect(() => {
    setHeaderContent(
      <PluginHeader
        onReload={handleReloadRuntime}
        loading={reloadLoading}
      />
    )
    return () => setHeaderContent(null)
  }, [setHeaderContent, handleReloadRuntime, reloadLoading])

  useEffect(() => {
    fetchPlugins()
  }, [fetchPlugins])

  const handleInstall = async (plugin: Plugin) => {
    try {
      setActionLoading(plugin.id)
      await installPlugin(plugin.id, {})
      toast.success(t('plugin.marketplacePage.toast.installSuccess'))
      fetchPlugins()
    } catch (error) {
      toast.error(t('plugin.marketplacePage.toast.installError'))
      console.error('Failed to install plugin:', error)
    } finally {
      setActionLoading(null)
    }
  }

  const handleUninstall = async (plugin: Plugin) => {
    try {
      setActionLoading(plugin.id)
      await uninstallPlugin(plugin.id)
      toast.success(t('plugin.marketplacePage.toast.uninstallSuccess'))
      fetchPlugins()
    } catch (error) {
      toast.error(t('plugin.marketplacePage.toast.uninstallError'))
      console.error('Failed to uninstall plugin:', error)
    } finally {
      setActionLoading(null)
    }
  }

  const handleToggleEnabled = async (plugin: Plugin, enabled: boolean) => {
    try {
      setActionLoading(plugin.id)
      await setPluginEnabled(plugin.id, enabled)
      toast.success(
        enabled ? t('plugin.marketplacePage.toast.enableSuccess') : t('plugin.marketplacePage.toast.disableSuccess')
      )
      setPlugins((prev) =>
        prev.map((item) =>
          item.id === plugin.id ? { ...item, enabled } : item
        )
      )
    } catch (error) {
      toast.error(
        enabled ? t('plugin.marketplacePage.toast.enableError') : t('plugin.marketplacePage.toast.disableError')
      )
      console.error('Failed to toggle plugin enabled:', error)
    } finally {
      setActionLoading(null)
    }
  }

  const resolvedList = useMemo(
    () =>
      plugins.map((plugin) => ({
        id: plugin.id,
        title: plugin.name,
        subtitle: `v${plugin.version}`,
        desc: plugin.description || t('plugin.marketplacePage.descriptionFallback'),
        icon: resolveIcon(plugin),
        iconType: resolveIconType(plugin),
        tags: resolveTags(plugin),
        installed: !!plugin.installed,
        enabled: plugin.enabled ?? false,
        mark: plugin.installed
          ? plugin.enabled
            ? t('plugin.marketplacePage.status.enabled')
            : t('plugin.marketplacePage.status.disabled')
          : null,
        raw: plugin,
      })),
    [plugins, t]
  )

  const counts = useMemo(() => {
    const allCount = resolvedList.length
    const aiCount = resolvedList.filter(item => item.tags?.includes('AI')).length
    const researchCount = resolvedList.filter(item => item.tags?.includes('Research')).length
    const nlpCount = resolvedList.filter(item => item.tags?.includes('NLP')).length

    return {
      all: allCount,
      ai: aiCount,
      research: researchCount,
      nlp: nlpCount,
    }
  }, [resolvedList])

  const filteredList = useMemo(() => {
    let result = [...resolvedList]
    if (searchQuery) {
      result = result.filter(item =>
        item.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.desc?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }
    // Category filtering (tags-based).
    if (activeCategory !== 'all') {
      if (activeCategory === 'ai') {
        result = result.filter(item => item.tags?.includes('AI'))
      } else if (activeCategory === 'research') {
        result = result.filter(item => item.tags?.includes('Research'))
      } else if (activeCategory === 'nlp') {
        result = result.filter(item => item.tags?.includes('NLP'))
      }
    }
    // Sorting.
    if (sortBy === 'name') {
      result.sort((a, b) => a.title.localeCompare(b.title))
    } else if (sortBy === 'popular') {
      result.sort((a, b) => (b.installed ? 1 : 0) - (a.installed ? 1 : 0))
    }
    return result
  }, [resolvedList, searchQuery, activeCategory, sortBy])

  return (
    <div className="flex flex-1 flex-col gap-4 p-4 md:p-6">
      {/* Category filters and search controls. */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-4">
        <Tabs defaultValue="all" value={activeCategory} onValueChange={setActiveCategory}>
          <TabsList>
            <TabsTrigger value="all" className="flex items-center">
              <Tag className="mr-2 h-4 w-4" />
              {t('plugin.marketplacePage.filters.all')}
              <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs">
                {counts.all}
              </span>
            </TabsTrigger>
            <TabsTrigger value="ai" className="flex items-center">
              <Tag className="mr-2 h-4 w-4" />
              {t('plugin.marketplacePage.filters.ai')}
              <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs">
                {counts.ai}
              </span>
            </TabsTrigger>
            <TabsTrigger value="research" className="flex items-center">
              <Tag className="mr-2 h-4 w-4" />
              {t('plugin.marketplacePage.filters.research')}
              <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs">
                {counts.research}
              </span>
            </TabsTrigger>
            <TabsTrigger value="nlp" className="flex items-center">
              <Tag className="mr-2 h-4 w-4" />
              {t('plugin.marketplacePage.filters.nlp')}
              <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs">
                {counts.nlp}
              </span>
            </TabsTrigger>
          </TabsList>
        </Tabs>

        <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
          <div className="relative w-full sm:w-[200px]">
            <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder={t('plugin.marketplacePage.searchPlaceholder')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8"
            />
          </div>
          <Select value={sortBy} onValueChange={setSortBy}>
            <SelectTrigger className="w-full sm:w-[140px]">
              <SlidersHorizontal className="mr-2 h-4 w-4" />
              <SelectValue placeholder={t('plugin.marketplacePage.sort.placeholder')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="default">
                <div className="flex items-center">
                  <Tag className="mr-2 h-4 w-4" />
                  {t('plugin.marketplacePage.sort.options.default')}
                </div>
              </SelectItem>
              <SelectItem value="name">
                <div className="flex items-center">
                  <Tag className="mr-2 h-4 w-4" />
                  {t('plugin.marketplacePage.sort.options.name')}
                </div>
              </SelectItem>
              <SelectItem value="popular">
                <div className="flex items-center">
                  <TrendingUp className="mr-2 h-4 w-4" />
                  {t('plugin.marketplacePage.sort.options.popular')}
                </div>
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid-box">
        {loading && (
          <div className="text-sm text-muted-foreground">{t('plugin.marketplacePage.loading')}</div>
        )}
        {!loading && filteredList.length === 0 && (
          <div className="text-sm text-muted-foreground">{t('plugin.marketplace.noPluginFound')}</div>
        )}
        {!loading &&
          filteredList.map((item, index) => {
            const plugin = item.raw as Plugin
            const isBusy = actionLoading === plugin.id
            const mainBtn = !item.installed ? (
              <Button size="sm" onClick={() => handleInstall(plugin)} disabled={isBusy}>
                {t('plugin.marketplacePage.actions.install')}
              </Button>
            ) : (
              <div className="flex items-center gap-2">
                <Switch
                  checked={!!item.enabled}
                  onCheckedChange={(checked) => handleToggleEnabled(plugin, checked)}
                  disabled={isBusy}
                />
                <Button size="sm" variant="outline" onClick={() => handleUninstall(plugin)} disabled={isBusy}>
                  {t('plugin.marketplacePage.actions.uninstall')}
                </Button>
              </div>
            )
            return <Item key={item.id} item={{ ...item, mainBtn }} index={index} />
          })}
      </div>
    </div>
  )
}

export default BoxPage
