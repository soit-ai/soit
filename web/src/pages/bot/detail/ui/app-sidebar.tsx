import * as React from 'react'
import { useCallback, useEffect, useState } from 'react'
import {
  SquareChartGantt,
  Settings2,
  SquareTerminal,
  LifeBuoy,
  SquareArrowOutUpRight,
  BotMessageSquare,
  ArrowLeft,
  ExternalLink,
  MessagesSquare,
  Captions,
  Blocks,
  SquareActivity,
  PencilRuler,
  ScanText,
  FilePenLine,
  ChartSpline,
  InfoIcon,
  StarIcon,
  AlertCircle,
  Share2,
  Users,
  Shield
} from 'lucide-react'

import { NavMain } from '@/components/nav/nav-main'
import { NavProjects } from '@/components/nav/nav-projects'
import { SidebarOptInForm } from '@/components/common/sidebar-opt-in-form'
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarRail, SidebarInput, useSidebar, SidebarTrigger } from '@/components/ui/sidebar'
import { useNavigate } from '@/hooks/use-navigate'
import { BoxHeader } from '@/components/ui/app/box-card'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import { useLocation } from 'react-router'

// This is sample data.

export interface NavSidebarProps extends React.ComponentProps<typeof Sidebar> {
  appid?: string
}

// 定义导航项类型
interface NavItem {
  title: string;
  url: string;
  icon: React.ElementType;
  description: string;
  isActive?: boolean;
  badge?: number | null;
}

export function NavSidebar({ ...props }: NavSidebarProps) {
  const { appid = '' } = props
  const navigate = useNavigate()
  const location = useLocation()
  const [navItems, setNavItems] = useState<NavItem[]>([])

  // 根据当前路径更新导航项的激活状态
  useEffect(() => {
    const currentPath = location.pathname
    
    // 导航菜单项定义
    const items: NavItem[] = [
      {
        title: 'Build',
        url: `/bot/${appid}/build`,
        icon: PencilRuler,
        description: '构建和配置机器人，设置提示词、知识库、工具和变量',
        isActive: currentPath.includes(`/bot/${appid}/build`)
      },
      {
        title: 'Logs',
        url: `/bot/${appid}/log`,
        icon: SquareChartGantt,
        description: '查看机器人运行日志、对话历史和错误记录',
        isActive: currentPath.includes(`/bot/${appid}/log`)
      },
      {
        title: 'Monitor',
        url: `/bot/${appid}/monitor`,
        icon: ChartSpline,
        description: '监控机器人性能指标、使用统计和响应时间',
        isActive: currentPath.includes(`/bot/${appid}/monitor`)
      },
      {
        title: 'Publish',
        url: `/bot/${appid}/publish`,
        icon: Share2,
        description: '发布机器人到应用商店，管理版本和访问权限',
        badge: 1,
        isActive: currentPath.includes(`/bot/${appid}/publish`)
      },
      {
        title: 'Setting',
        url: `/bot/${appid}/setting`,
        icon: Settings2,
        description: '管理机器人基本设置、API密钥和高级配置',
        isActive: currentPath.includes(`/bot/${appid}/setting`)
      },
    ]
    
    setNavItems(items)
  }, [location.pathname, appid])
  
  const botInfo = {
    id: appid,
    title: 'GPT-Researcher EN',
    subtitle: appid,
    icon: <BotMessageSquare color="blue" />,
    iconType: 'icon',
    desc: 'GPT-Researcher是一个专业的互联网主题研究助手。它能够高效地将一个主题分解为子问题，并从全面的角度提供专业的研究报告。',
    tags: ['AI', 'Research', 'NLP'],
    version: '1.2.0',
    lastUpdated: '2025-05-30',
    status: '已发布'
  }

  // 处理导航项点击
  const handleNavItemClick = useCallback((url: string) => {
    navigate(url)
  }, [navigate])
  
  // 处理菜单项悬停
  const handleNavItemHover = useCallback((item: NavItem) => {
    // 可以在这里添加悬停效果或预加载逻辑
    return item.description
  }, [])



  // 打开聊天窗口
  const openRunChat = useCallback(() => {
    navigate('/chat/' + appid)
  }, [navigate, appid])

  // 返回机器人列表
  const goBackToBotList = useCallback(() => {
    navigate('/bot')
  }, [navigate])

  // 渲染导航项
  const renderNavItem = (item: NavItem) => {
    return (
      <div key={item.title} className="mb-1">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant={item.isActive ? "secondary" : "ghost"}
              className={cn(
                "w-full justify-start transition-all duration-200",
                item.isActive && "bg-secondary"
              )}
              onClick={() => handleNavItemClick(item.url)}
            >
              <span className="flex items-center">
                {React.createElement(item.icon, { 
                  className: cn("h-4 w-4", item.isActive ? "text-primary" : "")
                })}
                <span className={cn("ml-2", item.isActive ? "font-medium" : "")}>{item.title}</span>
              </span>
              {item.badge ? (
                <Badge
                  className="ml-auto"
                  variant={item.isActive ? "default" : "secondary"}
                >
                  {item.badge}
                </Badge>
              ) : null}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right" className="max-w-[220px]">
            <p>{handleNavItemHover(item)}</p>
          </TooltipContent>
        </Tooltip>
      </div>
    )
  }



  return (
    <Sidebar className="hidden flex-1 md:flex" {...props}>
      <SidebarHeader className="mt-2">
        <BoxHeader
          title={botInfo.title}
          subtitle={botInfo.subtitle}
          icon={botInfo.icon}
          iconType={botInfo.iconType as 'icon'}
          iconHover={
            <ArrowLeft
              className="w-6 h-6 cursor-pointer"
              onClick={goBackToBotList}
            />
          }
        />
        <div className="px-3 py-2">
          <div className="rounded-lg border bg-card text-card-foreground shadow-sm p-3 mt-2">
            <div className="flex items-center mb-2">
              <InfoIcon className="mr-2 h-4 w-4 text-blue-500" />
              <h3 className="font-semibold text-sm">机器人信息</h3>
            </div>
            <p className="text-xs text-muted-foreground">{botInfo.desc}</p>
            <div className="flex flex-wrap gap-1 mt-2">
              {botInfo.tags.map(tag => (
                <Badge key={tag} variant="outline" className="text-xs">{tag}</Badge>
              ))}
            </div>
            <div className="mt-2 pt-2 border-t border-border">
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>版本:</span>
                <span>{botInfo.version}</span>
              </div>
              <div className="flex justify-between text-xs text-muted-foreground mt-1">
                <span>更新时间:</span>
                <span>{botInfo.lastUpdated}</span>
              </div>
              <div className="flex justify-between text-xs mt-1">
                <span>状态:</span>
                <span className="text-green-500 font-medium">{botInfo.status}</span>
              </div>
            </div>
          </div>
        </div>
        <Separator className="mt-1 mb-1" />
      </SidebarHeader>
      <SidebarContent>
        <ScrollArea className="h-full">
          <div className="px-1 py-2">
            <div className="space-y-1">
              {navItems.map(renderNavItem)}
            </div>
          </div>
        </ScrollArea>
      </SidebarContent>
      <SidebarFooter>
        <div className="p-3 space-y-2">
          <Button 
            className="w-full bg-sidebar-primary text-sidebar-primary-foreground shadow-none hover:bg-sidebar-primary/90" 
            onClick={openRunChat}
          >
            运行聊天 <MessagesSquare className="ml-2 h-4 w-4" />
          </Button>
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
