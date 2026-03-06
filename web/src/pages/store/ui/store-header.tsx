import React, { useEffect } from 'react'
import { useTranslation } from '@/i18n'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Search } from 'lucide-react'
import type { StoreCategory } from './store-types'
import { useNavLayout } from '@/components/layout/nav-layout'


function BoxHeader({ searchQuery, setSearchQuery, handleKeyDown }: { searchQuery: string; setSearchQuery: (query: string) => void; handleKeyDown: (e: React.KeyboardEvent<HTMLInputElement>) => void }) {
  return (
    <div className="flex flex-1 justify-between">
    <div>
      <h3 className="text-lg font-bold tracking-tight">应用商店</h3>
      <p className="text-sm text-muted-foreground mt-1">发现并安装插件、智能体、服务和应用</p>
    </div>
    <div className="relative w-full md:w-80">
      <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
      <Input
        type="search"
        placeholder="搜索商店..."
        className="pl-8"
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        onKeyDown={handleKeyDown}
      />
    </div>
  </div>
  )
}
interface StoreHeaderProps {
  activeCategory: StoreCategory
  onCategoryChange: (category: StoreCategory) => void
  onSearch: (query: string) => void
  categoryCounts?: Record<StoreCategory, number>
}


export function StoreHeader({ activeCategory, onCategoryChange, onSearch, categoryCounts = {} as Record<StoreCategory, number> }: StoreHeaderProps) {
  const { t } = useTranslation()
  const [searchQuery, setSearchQuery] = React.useState('')
  const { setHeaderContent } = useNavLayout()


  const handleSearch = () => {
    onSearch(searchQuery)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSearch()
    }
  }
  // 设置头部内容
  useEffect(() => {
    setHeaderContent(<BoxHeader searchQuery={searchQuery} setSearchQuery={setSearchQuery} handleKeyDown={handleKeyDown} />)
    return () => setHeaderContent(null)
  }, [setHeaderContent])

  return (
    <div className="store-header space-y-6 pb-6">

      <Tabs 
        value={activeCategory} 
        onValueChange={(value) => onCategoryChange(value as StoreCategory)} 
        className="w-full"
      >
        <TabsList className="inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground">
          <TabsTrigger value="all" className="px-3 flex items-center">
            All
            <span className="ml-1 rounded-full bg-muted-foreground/20 px-2 py-0.5 text-xs">
              {categoryCounts.all || 0}
            </span>
          </TabsTrigger>
          <TabsTrigger value="plugin" className="px-3 flex items-center">
            Plugins
            <span className="ml-1 rounded-full bg-muted-foreground/20 px-2 py-0.5 text-xs">
              {categoryCounts.plugin || 0}
            </span>
          </TabsTrigger>
          <TabsTrigger value="agent" className="px-3 flex items-center">
            Agents
            <span className="ml-1 rounded-full bg-muted-foreground/20 px-2 py-0.5 text-xs">
              {categoryCounts.agent || 0}
            </span>
          </TabsTrigger>
          <TabsTrigger value="service" className="px-3 flex items-center">
            Services
            <span className="ml-1 rounded-full bg-muted-foreground/20 px-2 py-0.5 text-xs">
              {categoryCounts.service || 0}
            </span>
          </TabsTrigger>
          <TabsTrigger value="application" className="px-3 flex items-center">
            Applications
            <span className="ml-1 rounded-full bg-muted-foreground/20 px-2 py-0.5 text-xs">
              {categoryCounts.application || 0}
            </span>
          </TabsTrigger>
          <TabsTrigger value="template" className="px-3 flex items-center">
            Templates
            <span className="ml-1 rounded-full bg-muted-foreground/20 px-2 py-0.5 text-xs">
              {categoryCounts.template || 0}
            </span>
          </TabsTrigger>
          <TabsTrigger value="model" className="px-3 flex items-center">
            Models
            <span className="ml-1 rounded-full bg-muted-foreground/20 px-2 py-0.5 text-xs">
              {categoryCounts.model || 0}
            </span>
          </TabsTrigger>
        </TabsList>
      </Tabs>
    </div>
  )
}
