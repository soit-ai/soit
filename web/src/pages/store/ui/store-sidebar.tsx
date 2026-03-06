import React, { useCallback } from 'react'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import {
  ShoppingBagIcon,
  TagIcon,
  PackageIcon,
  BotIcon,
  ServerIcon,
  LayoutTemplateIcon,
  SearchIcon,
  StarIcon,
  TrendingUpIcon,
  ClockIcon,
  HeartIcon,
  CheckCircleIcon,
  InfoIcon,
  ChevronRightIcon,
  ChevronDownIcon
} from 'lucide-react'
import { useState } from 'react'
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarInput, SidebarRail, SidebarTrigger } from '@/components/ui/sidebar'
import type { StoreCategory } from './store-types'

interface StoreSidebarProps {
  activeCategory?: StoreCategory;
  onCategoryChange?: (category: StoreCategory) => void;
  newItemsCount?: number;
}

// 定义侧边栏菜单项类型
interface MenuItem {
  id: StoreCategory;
  icon: React.ReactNode;
  label: string;
  description: string;
  badge?: number | null;
  section: 'main' | 'categories';
}

export function StoreSidebar({
  activeCategory = 'all',
  onCategoryChange,
  newItemsCount = 0,
  ...props
}: StoreSidebarProps & React.ComponentProps<typeof Sidebar>) {
  const { t } = useTranslation()
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    main: true,
    categories: true
  })

  // 菜单项定义
  const menuItems: MenuItem[] = [
    {
      id: 'all',
      icon: <ShoppingBagIcon className="h-4 w-4" />,
      label: '全部',
      description: '浏览所有商店项目',
      section: 'main'
    },
    {
      id: 'plugin',
      icon: <PackageIcon className="h-4 w-4" />,
      label: '插件',
      description: '浏览可用的插件',
      section: 'categories'
    },
    {
      id: 'agent',
      icon: <BotIcon className="h-4 w-4" />,
      label: '智能体',
      description: '浏览可用的智能体',
      section: 'categories'
    },
    {
      id: 'service',
      icon: <ServerIcon className="h-4 w-4" />,
      label: '服务',
      description: '浏览可用的服务',
      section: 'categories'
    },
    {
      id: 'application',
      icon: <PackageIcon className="h-4 w-4" />,
      label: '应用',
      description: '浏览可用的应用',
      section: 'categories'
    },
    {
      id: 'model',
      icon: <ServerIcon className="h-4 w-4" />,
      label: '大模型',
      description: '浏览可用的大模型服务',
      badge: 5,
      section: 'categories'
    },
    {
      id: 'template',
      icon: <LayoutTemplateIcon className="h-4 w-4" />,
      label: '模板',
      description: '浏览可用的模板',
      section: 'categories'
    }
  ]

  // 处理菜单项点击
  const handleMenuItemClick = useCallback((id: StoreCategory) => {
    if (onCategoryChange) {
      onCategoryChange(id)
    }
  }, [onCategoryChange])

  // 处理搜索输入
  const handleSearchInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value)
  }, [])

  // 切换分组展开/折叠
  const toggleSection = useCallback((section: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }))
  }, [])

  // 渲染菜单项
  const renderMenuItem = (item: MenuItem) => {
    const isActive = activeCategory === item.id

    return (
      <div key={item.id} className="mb-1">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant={isActive ? "secondary" : "ghost"}
              className={cn(
                "w-full justify-start",
                isActive && "bg-secondary"
              )}
              onClick={() => handleMenuItemClick(item.id)}
            >
              <span className="flex items-center">
                {item.icon}
                <span className="ml-2">{item.label}</span>
              </span>
              {item.badge ? (
                <Badge
                  className="ml-auto"
                  variant={isActive ? "default" : "secondary"}
                >
                  {item.badge}
                </Badge>
              ) : null}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>{item.description}</p>
          </TooltipContent>
        </Tooltip>
      </div>
    )
  }

  // 渲染分组标题
  const renderSectionTitle = (title: string, section: string) => {
    return (
      <div
        className="flex items-center px-2 mb-2 cursor-pointer group"
      >
        <h2 className="pl-2 text-sm font-semibold tracking-tight text-muted-foreground transition-colors">
          {title}
        </h2>
      </div>
    )
  }

  // 获取各分组菜单项
  const mainMenuItems = menuItems.filter(item => item.section === 'main')
  const categoryMenuItems = menuItems.filter(item => item.section === 'categories')

  // 渲染推荐项目
  const renderRecommendedSection = () => {
    return (
      <div className="px-2 py-2">
        <div className="rounded-lg border bg-card text-card-foreground shadow-sm p-3">
          <div className="flex flex-col space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <StarIcon className="mr-2 h-4 w-4 text-yellow-500" />
                <h3 className="font-semibold">推荐项目</h3>
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="flex items-center">
                  <BotIcon className="mr-1 h-3 w-3" />
                  智能助手
                </span>
                <Badge variant="outline" className="text-xs">热门</Badge>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="flex items-center">
                  <ServerIcon className="mr-1 h-3 w-3" />
                  文本生成API
                </span>
                <Badge variant="outline" className="text-xs">新品</Badge>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="flex items-center">
                  <PackageIcon className="mr-1 h-3 w-3" />
                  数据分析插件
                </span>
                <Badge variant="outline" className="text-xs">推荐</Badge>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <Sidebar className="hidden flex-1 md:flex" {...props}>
      <SidebarHeader className="mt-0">
        <div className="flex w-full items-center justify-between mb-2 px-2">
          <div className="text-lg font-medium text-foreground">商店</div>
          <SidebarTrigger className="-mr-1" />
        </div>
        <SidebarInput placeholder="搜索商店..." className="mx-2 w-auto"/>
      </SidebarHeader>
      <SidebarContent>
        <ScrollArea className="flex-1 overflow-auto">
          <div className="w-full">
            <div className="px-2 py-2">
              {renderSectionTitle('浏览', 'main')}
              {expandedSections.main && (
                <div className="space-y-1">
                  {mainMenuItems.map(renderMenuItem)}
                </div>
              )}
            </div>

            <div className="px-2 py-2">
              {renderSectionTitle('分类', 'categories')}
              {expandedSections.categories && (
                <div className="space-y-1">
                  {categoryMenuItems.map(renderMenuItem)}
                </div>
              )}
            </div>
          </div>
        </ScrollArea>
      </SidebarContent>
      <SidebarFooter>
        {renderRecommendedSection()}
        <div className="flex items-center justify-between p-2">
          <div className="flex items-center text-sm text-muted-foreground">
            <InfoIcon className="mr-1 h-4 w-4" />
            <span>共{newItemsCount}个新项目</span>
          </div>
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
