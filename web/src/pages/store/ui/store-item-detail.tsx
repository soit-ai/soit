import React from 'react'
import { useTranslation } from '@/i18n'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'
import { Star, Download, Calendar, Check, MessageSquare } from 'lucide-react'
import type { StoreItemProps } from './store-item-card'

interface StoreItemDetailProps {
  item: StoreItemProps
  onClose: () => void
  onInstall: (id: string) => void
}

export function StoreItemDetail({ item, onClose, onInstall }: StoreItemDetailProps) {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = React.useState('overview')

  const typeColors = {
    plugin: 'bg-blue-100 text-blue-800 dark:bg-blue-800 dark:text-blue-100',
    agent: 'bg-purple-100 text-purple-800 dark:bg-purple-800 dark:text-purple-100',
    service: 'bg-amber-100 text-amber-800 dark:bg-amber-800 dark:text-amber-100',
    template: 'bg-green-100 text-green-800 dark:bg-green-800 dark:text-green-100',
    'model-provider': 'bg-indigo-100 text-indigo-800 dark:bg-indigo-800 dark:text-indigo-100',
    model: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-800 dark:text-indigo-100'
  }

  // 模拟数据
  const screenshots = [
    { id: '1', url: 'https://placehold.co/600x400/png', alt: 'Screenshot 1' },
    { id: '2', url: 'https://placehold.co/600x400/png', alt: 'Screenshot 2' },
    { id: '3', url: 'https://placehold.co/600x400/png', alt: 'Screenshot 3' },
  ]

  const reviews = [
    { id: '1', author: '用户A', rating: 5, comment: '非常好用的插件，提高了我的工作效率！', date: '2025-05-20' },
    { id: '2', author: '用户B', rating: 4, comment: '功能强大，界面友好，推荐使用。', date: '2025-05-15' },
    { id: '3', author: '用户C', rating: 5, comment: '安装简单，使用方便，值得购买。', date: '2025-05-10' },
  ]

  return (
    <div className="store-item-detail flex h-full flex-col relative">
      <div className="flex items-start justify-between p-6 border-b">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <h2 className="text-2xl font-bold">{item.title}</h2>
            <Badge className={typeColors[item.type]}>
              {item.type === 'plugin' ? '插件' : 
               item.type === 'agent' ? '智能体' : 
               item.type === 'service' ? '服务' : 
               item.type === 'model' ? '大模型' : 
               '模板'}
            </Badge>
            {item.isPremium && (
              <Badge variant="outline" className="bg-amber-100 text-amber-800 dark:bg-amber-800 dark:text-amber-100">
                高级版
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-3 mb-2">
            <p className="text-muted-foreground flex items-center">
              <span className="font-medium text-foreground mr-1">开发者:</span> {item.author}
            </p>
            <p className="text-muted-foreground flex items-center">
              <span className="font-medium text-foreground mr-1">版本:</span> {item.version || '1.0.0'}
            </p>
          </div>
          <p className="text-sm text-muted-foreground">最后更新: {item.updatedAt || '2025-05-01'}</p>
        </div>
        <div className="flex flex-col items-end gap-2">
          {item.price && (
            <span className="text-lg font-bold text-green-600 dark:text-green-400">
              {item.price === 0 ? '免费' : `¥${item.price}`}
            </span>
          )}
        </div>
      </div>

      <div className="relative aspect-video w-full overflow-hidden bg-muted border-y">
        <img 
          src={item.imageUrl} 
          alt={item.title} 
          className="h-full w-full object-cover"
        />
        <div className="absolute bottom-0 right-0 bg-black/50 text-white px-3 py-1 text-xs rounded-tl-md">
          点击查看更多截图
        </div>
      </div>

      <div className="flex items-center justify-between p-6 border-b">
        <div className="grid grid-cols-3 gap-6 w-full">
          <div className="flex flex-col items-center justify-center p-3 rounded-lg bg-muted/30">
            <div className="flex items-center mb-1">
              <Star className="mr-1 h-5 w-5 fill-current text-yellow-500" />
              <span className="text-xl font-bold">{item.rating.toFixed(1)}</span>
            </div>
            <span className="text-xs text-muted-foreground">用户评分</span>
          </div>
          
          <div className="flex flex-col items-center justify-center p-3 rounded-lg bg-muted/30">
            <div className="flex items-center mb-1">
              <Download className="mr-1 h-5 w-5 text-blue-500" />
              <span className="text-xl font-bold">{item.downloads > 1000 ? `${(item.downloads / 1000).toFixed(1)}k` : item.downloads}</span>
            </div>
            <span className="text-xs text-muted-foreground">下载次数</span>
          </div>
          
          <div className="flex flex-col items-center justify-center p-3 rounded-lg bg-muted/30">
            <div className="flex items-center mb-1">
              <Calendar className="mr-1 h-5 w-5 text-green-500" />
              <span className="text-xl font-bold">{item.updatedAt || '2025-05-01'}</span>
            </div>
            <span className="text-xs text-muted-foreground">更新日期</span>
          </div>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1">
        <TabsList className="grid w-full grid-cols-4 px-6">
          <TabsTrigger value="overview">概览</TabsTrigger>
          <TabsTrigger value="features">功能</TabsTrigger>
          <TabsTrigger value="screenshots">截图</TabsTrigger>
          <TabsTrigger value="reviews">评价</TabsTrigger>
        </TabsList>
        
        <div className="flex-1 overflow-auto p-6">
          <TabsContent value="overview" className="mt-0">
            <div className="space-y-6">
              {/* 应用简介 */}
              <div className="space-y-3">
                <h3 className="text-lg font-medium flex items-center gap-2">
                  <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-primary/10 text-primary">
                    1
                  </span>
                  应用简介
                </h3>
                <div className="pl-8">
                  <p className="text-base">{item.description}</p>
                  <p className="mt-2 text-muted-foreground">
                    Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.
                  </p>
                </div>
              </div>
              
              {/* 使用场景 */}
              <div className="space-y-3">
                <h3 className="text-lg font-medium flex items-center gap-2">
                  <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-primary/10 text-primary">
                    2
                  </span>
                  使用场景
                </h3>
                <div className="pl-8 grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 border rounded-lg bg-muted/20">
                    <h4 className="font-medium mb-2">个人用户</h4>
                    <p className="text-sm text-muted-foreground">适用于个人用户的日常工作和学习，提高效率和体验。</p>
                  </div>
                  <div className="p-4 border rounded-lg bg-muted/20">
                    <h4 className="font-medium mb-2">企业用户</h4>
                    <p className="text-sm text-muted-foreground">为企业提供专业的解决方案，提升团队协作和工作效率。</p>
                  </div>
                </div>
              </div>
              
              {/* 标签和分类 */}
              <div className="space-y-3">
                <h3 className="text-lg font-medium flex items-center gap-2">
                  <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-primary/10 text-primary">
                    3
                  </span>
                  标签和分类
                </h3>
                <div className="pl-8">
                  <div className="flex flex-wrap gap-2 mb-4">
                    {item.tags.map((tag) => (
                      <Badge key={tag} variant="outline" className="px-3 py-1">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">兼容性:</span>
                    <Badge variant="outline" className="bg-green-100 text-green-800 dark:bg-green-800 dark:text-green-100">
                      所有平台
                    </Badge>
                  </div>
                </div>
              </div>
            </div>
          </TabsContent>
          
          <TabsContent value="features" className="mt-0">
            <div className="space-y-6">
              {/* 主要功能 */}
              <div className="space-y-3">
                <h3 className="text-lg font-medium">主要功能</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 border rounded-lg bg-muted/20 flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600">
                      1
                    </div>
                    <div>
                      <h4 className="font-medium mb-1">功能特点 1</h4>
                      <p className="text-sm text-muted-foreground">详细的功能描述，包含该功能的优势和使用方式。</p>
                    </div>
                  </div>
                  <div className="p-4 border rounded-lg bg-muted/20 flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center text-purple-600">
                      2
                    </div>
                    <div>
                      <h4 className="font-medium mb-1">功能特点 2</h4>
                      <p className="text-sm text-muted-foreground">详细的功能描述，包含该功能的优势和使用方式。</p>
                    </div>
                  </div>
                  <div className="p-4 border rounded-lg bg-muted/20 flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center text-amber-600">
                      3
                    </div>
                    <div>
                      <h4 className="font-medium mb-1">功能特点 3</h4>
                      <p className="text-sm text-muted-foreground">详细的功能描述，包含该功能的优势和使用方式。</p>
                    </div>
                  </div>
                  <div className="p-4 border rounded-lg bg-muted/20 flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center text-green-600">
                      4
                    </div>
                    <div>
                      <h4 className="font-medium mb-1">功能特点 4</h4>
                      <p className="text-sm text-muted-foreground">详细的功能描述，包含该功能的优势和使用方式。</p>
                    </div>
                  </div>
                </div>
              </div>
              
              {/* 技术规格 */}
              <div className="space-y-3">
                <h3 className="text-lg font-medium">技术规格</h3>
                <div className="overflow-hidden border rounded-lg">
                  <table className="min-w-full divide-y divide-border">
                    <tbody className="divide-y divide-border">
                      <tr>
                        <td className="px-4 py-3 text-sm font-medium bg-muted/50 w-1/3">版本</td>
                        <td className="px-4 py-3 text-sm">{item.version || '1.0.0'}</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 text-sm font-medium bg-muted/50">兼容性</td>
                        <td className="px-4 py-3 text-sm">支持所有主流浏览器和设备</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 text-sm font-medium bg-muted/50">授权协议</td>
                        <td className="px-4 py-3 text-sm">MIT</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 text-sm font-medium bg-muted/50">开发语言</td>
                        <td className="px-4 py-3 text-sm">TypeScript, React</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </TabsContent>
          
          <TabsContent value="screenshots" className="mt-0">
            <div className="space-y-6">
              <h3 className="text-lg font-medium">应用截图</h3>
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                {screenshots.map((screenshot) => (
                  <div key={screenshot.id} className="overflow-hidden rounded-lg border shadow-sm hover:shadow-md transition-shadow">
                    <div className="aspect-video overflow-hidden">
                      <img 
                        src={screenshot.url} 
                        alt={screenshot.alt} 
                        className="h-full w-full object-cover hover:scale-105 transition-transform duration-300"
                      />
                    </div>
                    <div className="p-3 bg-muted/20">
                      <p className="text-sm font-medium">{screenshot.alt}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </TabsContent>
          
          <TabsContent value="reviews" className="mt-0">
            <div className="space-y-6">
              {/* 评分概览 */}
              <div className="flex flex-col md:flex-row gap-6 p-4 border rounded-lg bg-muted/20">
                <div className="flex flex-col items-center justify-center">
                  <span className="text-4xl font-bold">{item.rating.toFixed(1)}</span>
                  <div className="flex my-2">
                    {Array(5).fill(0).map((_, i) => (
                      <Star 
                        key={i} 
                        className={`h-5 w-5 ${i < Math.round(item.rating) ? 'fill-current text-yellow-500' : 'text-gray-300'}`} 
                      />
                    ))}
                  </div>
                  <span className="text-sm text-muted-foreground">基于 {reviews.length} 条评价</span>
                </div>
                
                <div className="flex-1 space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm w-8">5星</span>
                    <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                      <div className="h-full bg-yellow-500" style={{ width: '70%' }}></div>
                    </div>
                    <span className="text-sm w-8">70%</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm w-8">4星</span>
                    <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                      <div className="h-full bg-yellow-500" style={{ width: '20%' }}></div>
                    </div>
                    <span className="text-sm w-8">20%</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm w-8">3星</span>
                    <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                      <div className="h-full bg-yellow-500" style={{ width: '5%' }}></div>
                    </div>
                    <span className="text-sm w-8">5%</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm w-8">2星</span>
                    <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                      <div className="h-full bg-yellow-500" style={{ width: '3%' }}></div>
                    </div>
                    <span className="text-sm w-8">3%</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm w-8">1星</span>
                    <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                      <div className="h-full bg-yellow-500" style={{ width: '2%' }}></div>
                    </div>
                    <span className="text-sm w-8">2%</span>
                  </div>
                </div>
                
                <div className="flex flex-col items-center justify-center">
                  <Button size="lg" className="gap-1 mb-2">
                    <MessageSquare className="h-4 w-4" />
                    写评价
                  </Button>
                  <span className="text-xs text-muted-foreground">分享您的使用体验</span>
                </div>
              </div>
              
              {/* 用户评价列表 */}
              <div className="space-y-4">
                <h3 className="text-lg font-medium">用户评价</h3>
                <div className="space-y-6">
                  {reviews.map((review) => (
                    <div key={review.id} className="p-4 border rounded-lg">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary font-medium">
                            {review.author.charAt(0)}
                          </div>
                          <div>
                            <div className="font-medium">{review.author}</div>
                            <div className="text-xs text-muted-foreground">{review.date}</div>
                          </div>
                        </div>
                        <div className="flex">
                          {Array(5).fill(0).map((_, i) => (
                            <Star 
                              key={i} 
                              className={`h-4 w-4 ${i < review.rating ? 'fill-current text-yellow-500' : 'text-gray-300'}`} 
                            />
                          ))}
                        </div>
                      </div>
                      <p className="text-sm">{review.comment}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </TabsContent>
        </div>
      </Tabs>
      
      {/* 底部固定操作栏 */}
      <div className="absolute bottom-0 left-0 right-0 border-t bg-background p-4 flex justify-between items-center shadow-md">
        <div className="flex items-center gap-2">
          {item.price !== undefined && (
            <span className="text-lg font-bold text-green-600 dark:text-green-400">
              {item.price === 0 ? '免费' : `¥${item.price}`}
            </span>
          )}
        </div>
        <div>
          {item.isInstalled ? (
            <Button variant="outline" className="gap-2" onClick={() => onInstall(item.id)}>
              <Check className="h-4 w-4" />
              已安装
            </Button>
          ) : (
            <Button className="gap-2" size="lg" onClick={() => onInstall(item.id)}>
              <Download className="h-4 w-4" />
              安装
            </Button>
          )}
        </div>
      </div>
      
      {/* 底部空白区域，防止内容被固定操作栏遮挡 */}
      <div className="h-20"></div>
    </div>
  )
}
