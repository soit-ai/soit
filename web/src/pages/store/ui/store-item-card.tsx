import React from 'react'
import { useTranslation } from '@/i18n'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Star, Download, Check, Flame } from 'lucide-react'
import { AppIcon } from '@/components/ui/app/app-icon'

export interface StoreItemProps {
  id: string
  title: string
  description: string
  author: string
  type: 'plugin' | 'agent' | 'service' | 'template' | 'model-provider' | 'model'
  rating: number
  downloads: number
  tags: string[]
  imageUrl: string
  isInstalled?: boolean
  isPremium?: boolean
  price?: number
  version?: string
  updatedAt?: string
  onInstall?: (id: string) => void
  onView?: (id: string) => void
}

export function StoreItemCard({
  id,
  title,
  description,
  author,
  type,
  rating,
  downloads,
  tags,
  imageUrl,
  isInstalled = false,
  onInstall,
  onView,
}: StoreItemProps) {
  const { t } = useTranslation()
  
  const handleInstall = () => {
    if (onInstall) onInstall(id)
  }
  
  const handleView = () => {
    if (onView) onView(id)
  }
  
  const typeColors = {
    plugin: 'bg-blue-100 text-blue-800 dark:bg-blue-800 dark:text-blue-100',
    agent: 'bg-purple-100 text-purple-800 dark:bg-purple-800 dark:text-purple-100',
    service: 'bg-amber-100 text-amber-800 dark:bg-amber-800 dark:text-amber-100',
    template: 'bg-green-100 text-green-800 dark:bg-green-800 dark:text-green-100',
    model: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-800 dark:text-indigo-100',
    'model-provider': 'bg-indigo-100 text-indigo-800 dark:bg-indigo-800 dark:text-indigo-100',
  }

  const typeLabels = {
    plugin: '插件',
    agent: '智能体',
    service: '服务',
    template: '模板',
    model: '模型',
    'model-provider': '模型服务商'
  }

  // 渲染安装/查看按钮
  const renderButton = () => {
    if (isInstalled) {
      return (
        <Button variant="outline" size="sm" className="h-6 gap-1" onClick={handleView}>
          <Check className="h-3.5 w-3.5" />
          已安装
        </Button>
      )
    } else {
      return (
        <Button size="sm" className="h-6" onClick={handleInstall}>
          安装
        </Button>
      )
    }
  }

  // 获取图标
  const getIcon = () => {
    if (imageUrl) {
      return imageUrl
    } else {
      // 根据类型返回默认图标
      const iconMap = {
        plugin: '🔌',
        agent: '🤖',
        service: '⚙️',
        template: '📄',
        model: '🧠',
        'model-provider': '💻'
      }
      return iconMap[type] || '📦'
    }
  }

  // 是否是热门项目
  const isHot = downloads > 5000

  return (
    <Card className="py-1 gap-0 hover:shadow-md transition-all">
      <CardHeader className="p-3 relative">
        <div className="flex flex-row justify-between items-center overflow-hidden">
          <div className="flex flex-row h-full items-center overflow-hidden">
            <AppIcon 
              icon={imageUrl ? imageUrl : getIcon()} 
              type={imageUrl ? 'image' : 'emoji'} 
            />
            <div className="pl-2 space-y-1 overflow-hidden">
              <CardTitle className="text-sm">{title}</CardTitle>
              <CardDescription className="text-xs truncate overflow-hidden">
                {author} • <Star className="inline h-3 w-3 fill-current text-yellow-500" /> {rating.toFixed(1)} • <Download className="inline h-3 w-3" /> {downloads > 1000 ? `${(downloads / 1000).toFixed(1)}k` : downloads}
              </CardDescription>
            </div>
          </div>
        </div>
        {isHot && (
          <div className="absolute top-[-10px] right-[-5px]">
            <Flame color="red" size={18} />
          </div>
        )}
        <Badge className={`absolute top-3 right-0 text-[10px] font-normal text-center ${typeColors[type]}`}>
          {typeLabels[type]}
        </Badge>
      </CardHeader>
      <CardContent className="p-3 pt-0 pb-0">
        <div className="flex flex-row h-[66px] justify-start items-start overflow-hidden">
          <p className="text-xs text-muted-foreground text-wrap line-clamp-3">{description}</p>
        </div>
      </CardContent>
      <CardFooter className="p-3 pt-1">
        <div className="flex flex-row flex-1 justify-between pt-1">
          <div className="flex flex-row flex-1 gap-1 justify-start items-center flex-wrap">
            {tags.slice(0, 3).map((tag) => (
              <Badge key={tag} variant="secondary" className="h-4 pl-1 pr-1 text-[10px] font-normal text-center">
                {tag}
              </Badge>
            ))}
            {tags.length > 3 && (
              <Badge variant="secondary" className="h-4 pl-1 pr-1 text-[10px] font-normal text-center">
                +{tags.length - 3}
              </Badge>
            )}
          </div>
          <div className="flex flex-row gap-2 h-6">
            <span className="text-xs text-green-600 dark:text-green-400 self-center"></span>
            {renderButton()}
          </div>
        </div>
      </CardFooter>
    </Card>
  )
}
