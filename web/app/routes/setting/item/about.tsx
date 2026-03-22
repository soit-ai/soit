import { useTranslation } from '@/i18n'
import { useState } from 'react'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { toast } from '@/hooks/use-toast'
import { ExternalLink, Github, Mail, MessageSquare, Twitter, Heart, Info, CheckCircle2, AlertTriangle, Bug, Zap, Gift } from 'lucide-react'

function Page() {
  const { t } = useTranslation()
  
  // 产品版本信息
  const appVersion = "1.0.0"
  const lastUpdated = "2025-05-30"
  const appName = t('app.name')
  
  // 团队成员信息
  const teamMembers = [
    { id: 1, name: "张三", role: "创始人 & CEO", avatar: "/avatars/01.png" },
    { id: 2, name: "李四", role: "CTO", avatar: "/avatars/02.png" },
    { id: 3, name: "王五", role: "产品经理", avatar: "/avatars/03.png" },
    { id: 4, name: "赵六", role: "UI/UX 设计师", avatar: "/avatars/04.png" },
    { id: 5, name: "钱七", role: "高级开发工程师", avatar: "/avatars/05.png" },
  ]
  
  // 版本历史
  const versionHistory = [
    { version: "1.0.0", date: "2025-05-30", title: "正式版发布", description: "首个正式版本发布，包含所有核心功能" },
    { version: "0.9.0", date: "2025-04-15", title: "公开测试版", description: "修复了大量bug，优化了用户体验" },
    { version: "0.8.0", date: "2025-03-01", title: "内部测试版", description: "添加了高级分析功能和API集成" },
    { version: "0.7.0", date: "2025-02-10", title: "内部测试版", description: "重新设计了用户界面，提升了性能" },
    { version: "0.5.0", date: "2025-01-05", title: "内部测试版", description: "实现了基础功能和核心架构" },
  ]
  
  // 处理复制系统信息
  const handleCopySystemInfo = () => {
    const systemInfo = `
      应用名称: ${appName}
      版本: ${appVersion}
      最后更新: ${lastUpdated}
      操作系统: ${navigator.platform}
      浏览器: ${navigator.userAgent}
    `
    
    navigator.clipboard.writeText(systemInfo.trim())
    
    toast({
      title: "系统信息已复制",
      description: "系统信息已复制到剪贴板",
    })
  }
  
  // 处理发送反馈
  const handleSendFeedback = () => {
    // 这里应该有API调用来发送反馈
    console.log('发送反馈')
    
    toast({
      title: "感谢您的反馈",
      description: "我们已收到您的反馈，感谢您帮助我们改进产品",
    })
  }
  
  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold tracking-tight">关于我们</h3>
          <p className="text-sm text-muted-foreground mt-1">了解产品信息、团队和联系方式</p>
        </div>
      </div>

      <Tabs defaultValue="product" className="w-full">
        <TabsList className="mb-4 grid w-full max-w-md grid-cols-4">
          <TabsTrigger value="product">产品信息</TabsTrigger>
          <TabsTrigger value="team">团队介绍</TabsTrigger>
          <TabsTrigger value="version">版本历史</TabsTrigger>
          <TabsTrigger value="contact">联系我们</TabsTrigger>
        </TabsList>
        
        {/* 产品信息标签页 */}
        <TabsContent value="product">
          <Card>
            <CardHeader>
              <CardTitle>产品信息</CardTitle>
              <CardDescription>了解我们的产品和使命</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex flex-col items-center space-y-4 text-center sm:items-start sm:text-left">
                <div className="space-y-2">
                  <h3 className="text-2xl font-bold">{appName}</h3>
                  <p className="text-muted-foreground">
                    一个面向未来的智能化平台，为您提供强大的数据分析和决策支持。
                  </p>
                </div>
                
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 mt-4 w-full">
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base">当前版本</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">{appVersion}</div>
                      <p className="text-xs text-muted-foreground">最后更新于 {lastUpdated}</p>
                    </CardContent>
                  </Card>
                  
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base">许可证</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">Apache</div>
                      <p className="text-xs text-muted-foreground">开源许可证</p>
                    </CardContent>
                  </Card>
                  
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base">技术支持</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">24/7</div>
                      <p className="text-xs text-muted-foreground">全天候支持</p>
                    </CardContent>
                  </Card>
                </div>
                
                <div className="space-y-4 mt-6 w-full">
                  <h4 className="text-lg font-semibold">核心功能</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="flex items-start space-x-2">
                      <CheckCircle2 className="h-5 w-5 text-green-500 mt-0.5" />
                      <div>
                        <h5 className="font-medium">智能分析</h5>
                        <p className="text-sm text-muted-foreground">使用先进的AI算法分析您的数据</p>
                      </div>
                    </div>
                    <div className="flex items-start space-x-2">
                      <CheckCircle2 className="h-5 w-5 text-green-500 mt-0.5" />
                      <div>
                        <h5 className="font-medium">实时协作</h5>
                        <p className="text-sm text-muted-foreground">与团队成员实时协作和共享</p>
                      </div>
                    </div>
                    <div className="flex items-start space-x-2">
                      <CheckCircle2 className="h-5 w-5 text-green-500 mt-0.5" />
                      <div>
                        <h5 className="font-medium">安全可靠</h5>
                        <p className="text-sm text-muted-foreground">企业级安全性和可靠性</p>
                      </div>
                    </div>
                    <div className="flex items-start space-x-2">
                      <CheckCircle2 className="h-5 w-5 text-green-500 mt-0.5" />
                      <div>
                        <h5 className="font-medium">开放集成</h5>
                        <p className="text-sm text-muted-foreground">与您已有的工具和系统无缝集成</p>
                      </div>
                    </div>
                  </div>
                </div>
                
                <Button onClick={handleCopySystemInfo} className="mt-6">
                  <Info className="mr-2 h-4 w-4" />
                  复制系统信息
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* 团队介绍标签页 */}
        <TabsContent value="team">
          <Card>
            <CardHeader>
              <CardTitle>团队介绍</CardTitle>
              <CardDescription>了解我们的团队成员</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {teamMembers.map((member) => (
                  <Card key={member.id}>
                    <CardContent className="pt-6 flex flex-col items-center text-center">
                      <Avatar className="h-20 w-20 mb-4">
                        <AvatarImage src={member.avatar} alt={member.name} />
                        <AvatarFallback>{member.name.substring(0, 1)}</AvatarFallback>
                      </Avatar>
                      <h3 className="text-lg font-bold">{member.name}</h3>
                      <p className="text-sm text-muted-foreground mb-4">{member.role}</p>
                      <div className="flex space-x-2">
                        <Button variant="ghost" size="icon">
                          <Twitter className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon">
                          <Github className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon">
                          <Mail className="h-4 w-4" />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* 版本历史标签页 */}
        <TabsContent value="version">
          <Card>
            <CardHeader>
              <CardTitle>版本历史</CardTitle>
              <CardDescription>查看产品的发展历程</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-8">
                {versionHistory.map((version, index) => (
                  <div key={version.version} className="relative pl-6 pb-8 last:pb-0">
                    {index < versionHistory.length - 1 && (
                      <div className="absolute left-2 top-2 bottom-0 w-[1px] bg-border" />
                    )}
                    <div className="absolute left-0 top-2 h-4 w-4 rounded-full bg-primary" />
                    <div>
                      <div className="flex items-baseline gap-2">
                        <h3 className="text-lg font-semibold">版本 {version.version}</h3>
                        <Badge variant="outline">{version.title}</Badge>
                      </div>
                      <p className="text-sm text-muted-foreground mt-1">{version.date}</p>
                      <p className="mt-2">{version.description}</p>
                      
                      {version.version === "1.0.0" && (
                        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div className="flex items-center space-x-2 rounded-md border p-2">
                            <Bug className="h-4 w-4 text-red-500" />
                            <span className="text-sm">修复了 35 个问题</span>
                          </div>
                          <div className="flex items-center space-x-2 rounded-md border p-2">
                            <Zap className="h-4 w-4 text-yellow-500" />
                            <span className="text-sm">添加了 12 个新功能</span>
                          </div>
                          <div className="flex items-center space-x-2 rounded-md border p-2">
                            <Gift className="h-4 w-4 text-blue-500" />
                            <span className="text-sm">改进了 8 个现有功能</span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* 联系我们标签页 */}
        <TabsContent value="contact">
          <Card>
            <CardHeader>
              <CardTitle>联系我们</CardTitle>
              <CardDescription>获取支持或提供反馈</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">客户支持</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center space-x-3">
                      <Mail className="h-5 w-5 text-muted-foreground" />
                      <span>support@example.com</span>
                    </div>
                    <div className="flex items-center space-x-3">
                      <MessageSquare className="h-5 w-5 text-muted-foreground" />
                      <span>在线聊天支持 (24/7)</span>
                    </div>
                    <Button className="w-full mt-2">
                      联系支持
                    </Button>
                  </CardContent>
                </Card>
                
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">反馈与建议</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-sm text-muted-foreground">
                      我们非常重视您的反馈。如果您有任何建议或发现了问题，请告诉我们。
                    </p>
                    <Button variant="outline" className="w-full" onClick={handleSendFeedback}>
                      <Heart className="mr-2 h-4 w-4 text-red-500" />
                      发送反馈
                    </Button>
                  </CardContent>
                </Card>
              </div>
              
              <div className="pt-4">
                <h3 className="text-lg font-medium mb-4">常见问题</h3>
                <Accordion type="single" collapsible className="w-full">
                  <AccordionItem value="item-1">
                    <AccordionTrigger>如何开始使用该产品？</AccordionTrigger>
                    <AccordionContent>
                      注册账户后，您可以按照我们的入门指南进行操作。我们提供了详细的文档和教程视频来帮助您快速上手。
                    </AccordionContent>
                  </AccordionItem>
                  <AccordionItem value="item-2">
                    <AccordionTrigger>产品是否提供免费试用？</AccordionTrigger>
                    <AccordionContent>
                      是的，我们提供14天的免费试用期，您可以在此期间体验所有功能。试用期结束后，您可以选择升级到付费计划或继续使用免费版（功能有限制）。
                    </AccordionContent>
                  </AccordionItem>
                  <AccordionItem value="item-3">
                    <AccordionTrigger>如何升级我的订阅？</AccordionTrigger>
                    <AccordionContent>
                      您可以在"账单管理"页面中升级您的订阅。我们提供多种计划供您选择，以满足不同的需求和预算。
                    </AccordionContent>
                  </AccordionItem>
                  <AccordionItem value="item-4">
                    <AccordionTrigger>我的数据是否安全？</AccordionTrigger>
                    <AccordionContent>
                      是的，我们非常重视数据安全。我们使用行业标准的加密技术来保护您的数据，并且我们不会在未经您同意的情况下与第三方共享您的信息。
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default Page
