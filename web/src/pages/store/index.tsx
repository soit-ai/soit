import React, { useState, useEffect, useCallback } from 'react'
import { useTranslation } from '@/i18n'

// 导入商店组件
import { StoreHeader } from './ui/store-header'
import { StoreFeatured } from './ui/store-featured'
import { StoreCategorySection } from './ui/store-category-section'
import { StoreItemDetail } from './ui/store-item-detail'
import { StoreItemCard } from './ui/store-item-card'
import { StoreSidebar } from './ui/store-sidebar'
import type { StoreItemProps } from './ui/store-item-card'
import type { FeaturedItemProps } from './ui/store-featured'
import type { StoreCategory, StoreFilterOptions } from './ui/store-types'

// 导入模拟数据
import {
  mockStoreItems,
  mockFeaturedItems,
  getRecommendedItems,
  getPopularItems,
  getNewestItems,
  filterItemsByCategory,
  filterItemsByQuery,
  getFreeItems
} from './ui/store-mock-data'

// 导入UI组件
import { Sheet, SheetContent } from '@/components/ui/sheet'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Button } from '@/components/ui/button'
import { NavLayout, NavHeader } from '@/components/layout/nav-layout'
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from '@/components/ui/breadcrumb'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { RefreshCwIcon } from 'lucide-react'

function StorePage() {
  const { t } = useTranslation()
  const [activeCategory, setActiveCategory] = useState<StoreCategory>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [items, setItems] = useState<StoreItemProps[]>(mockStoreItems)
  const [filterOptions, setFilterOptions] = useState<StoreFilterOptions>({ category: 'all', query: '', sort: 'popular' })
  const [detailItem, setDetailItem] = useState<StoreItemProps | null>(null)
  const [isDetailOpen, setIsDetailOpen] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [categoryCounts, setCategoryCounts] = useState<Record<StoreCategory, number>>({
    all: 0,
    plugin: 0,
    agent: 0,
    service: 0,
    application: 0,
    template: 0,
    model: 0
  })

  // 计算各分类的数量
  useEffect(() => {
    const counts = {
      all: mockStoreItems.length,
      plugin: mockStoreItems.filter(item => item.type === 'plugin').length,
      agent: mockStoreItems.filter(item => item.type === 'agent').length,
      service: mockStoreItems.filter(item => item.type === 'service').length,
      application: mockStoreItems.filter(item => item.type === 'application').length,
      template: mockStoreItems.filter(item => item.type === 'template').length,
      model: mockStoreItems.filter(item => item.type === 'model').length
    } as Record<StoreCategory, number>
    
    setCategoryCounts(counts)
  }, [mockStoreItems])

  // 处理类别变更
  const handleCategoryChange = useCallback((category: StoreCategory) => {
    setActiveCategory(category)
    if (category === 'all') {
      setItems(mockStoreItems)
    } else {
      setItems(filterItemsByCategory(mockStoreItems, category))
    }
  }, [])

  // 处理搜索
  const handleSearch = useCallback((query: string) => {
    setSearchQuery(query)
    if (query.trim() === '') {
      if (activeCategory === 'all') {
        setItems(mockStoreItems)
      } else {
        setItems(filterItemsByCategory(mockStoreItems, activeCategory))
      }
    } else {
      let filtered = mockStoreItems
      if (activeCategory !== 'all') {
        filtered = filterItemsByCategory(filtered, activeCategory)
      }
      setItems(filterItemsByQuery(filtered, query))
    }
  }, [activeCategory])

  // 处理排序和筛选
  const handleFilterChange = useCallback((options: StoreFilterOptions) => {
    setFilterOptions(options)
  }, [])

  // 处理安装
  const handleInstall = useCallback((id: string) => {
    console.log(`Installing item with id: ${id}`)
    // 在实际应用中，这里会调用安装API
  }, [])

  // 处理查看详情
  const handleViewDetail = useCallback((id: string) => {
    const item = items.find((item) => item.id === id)
    if (item) {
      setDetailItem(item)
      setIsDetailOpen(true)
    }
  }, [items])

  // 关闭详情
  const handleCloseDetail = useCallback(() => {
    setIsDetailOpen(false)
  }, [])

  // 刷新数据
  const handleRefreshData = useCallback(() => {
    setRefreshing(true)
    // 模拟刷新数据
    setTimeout(() => {
      setItems([...mockStoreItems])
      setRefreshing(false)
    }, 800)
  }, [])

  // 获取不同类别的项目
  const recommendedItems = getRecommendedItems(mockStoreItems)
  const popularItems = getPopularItems(mockStoreItems)
  const newestItems = getNewestItems(mockStoreItems)
  const freeItems = getFreeItems(mockStoreItems)
  
  // 获取模型服务商
  const modelProviders = filterItemsByCategory(mockStoreItems, 'model')

  // 渲染头部
  const renderHeader = useCallback(() => {
    return (
      <div className="flex flex-1 justify-between">
        <div className="flex items-center gap-2">
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem className="hidden md:block">
                <BreadcrumbLink>应用中心</BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator className="hidden md:block" />
              <BreadcrumbItem>
                <BreadcrumbPage>商店</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        </div>
        <div className="flex gap-2">
          <Button
            size={'sm'}
            variant={'outline'}
            title="刷新数据"
            onClick={handleRefreshData}
            disabled={refreshing}
          >
            <RefreshCwIcon size={16} className={refreshing ? 'animate-spin' : ''} />
          </Button>
        </div>
      </div>
    )
  }, [refreshing, handleRefreshData])

  // 渲染当前类别内容
  const renderCategoryContent = useCallback(() => {
    if (activeCategory === 'all') {
      return (
        <>
          {/* 大模型专区 */}
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-bold">大模型</h2>
              <Button variant="outline" size="sm" onClick={() => handleCategoryChange('model')}>
                查看全部
              </Button>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {modelProviders.slice(0, 4).map((item) => (
                <StoreItemCard
                  key={item.id}
                  {...item}
                  onInstall={handleInstall}
                  onView={handleViewDetail}
                />
              ))}
            </div>
          </div>

          {/* 推荐项目 */}
          <div className="space-y-4">
            <h2 className="text-xl font-bold">推荐</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {recommendedItems.map((item) => (
                <StoreItemCard
                  key={item.id}
                  {...item}
                  onInstall={handleInstall}
                  onView={handleViewDetail}
                />
              ))}
            </div>
          </div>

          {/* 热门项目 */}
          <div className="space-y-4">
            <h2 className="text-xl font-bold">热门</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {popularItems.map((item) => (
                <StoreItemCard
                  key={item.id}
                  {...item}
                  onInstall={handleInstall}
                  onView={handleViewDetail}
                />
              ))}
            </div>
          </div>

          {/* 最新项目 */}
          <div className="space-y-4">
            <h2 className="text-xl font-bold">最新</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {newestItems.map((item) => (
                <StoreItemCard
                  key={item.id}
                  {...item}
                  onInstall={handleInstall}
                  onView={handleViewDetail}
                />
              ))}
            </div>
          </div>
        </>
      )
    } else {
      return (
        <StoreCategorySection
          title={activeCategory === 'plugin' ? '插件' : 
                activeCategory === 'agent' ? '智能体' : 
                activeCategory === 'service' ? '服务' : 
                activeCategory === 'application' ? '应用' : 
                activeCategory === 'model' ? '大模型' : '模板'}
          items={items}
          onInstall={handleInstall}
          onView={handleViewDetail}
        />
      )
    }
  }, [activeCategory, items, modelProviders, recommendedItems, popularItems, newestItems, handleInstall, handleViewDetail, handleCategoryChange])

  return (
    <NavLayout left={<StoreSidebar activeCategory={activeCategory} onCategoryChange={handleCategoryChange} newItemsCount={newestItems.length} />} header={renderHeader()}>
      <div className="flex">
        {/* 主内容区域 */}
        <div className="flex-1 flex flex-col gap-4 p-4">
          {/* 商店头部搜索和分类 */}
          <StoreHeader 
            activeCategory={activeCategory} 
            onCategoryChange={(category: StoreCategory) => handleCategoryChange(category)} 
            onSearch={handleSearch}
            categoryCounts={categoryCounts}
          />
          
          {/* 移除了精选板块 */}
          
          {/* 主要内容区域 */}
          <div className="space-y-8">
            {renderCategoryContent()}
          </div>
        </div>
      </div>

      {/* 详情抽屉 */}
      <Sheet open={isDetailOpen} onOpenChange={setIsDetailOpen}>
        <SheetContent className="w-full sm:max-w-xl overflow-y-auto">
          <ScrollArea className="h-full">
            {detailItem && (
              <StoreItemDetail
                item={detailItem}
                onClose={() => setIsDetailOpen(false)}
                onInstall={handleInstall}
              />
            )}
          </ScrollArea>
        </SheetContent>
      </Sheet>
    </NavLayout>
  )
}

export default StorePage
