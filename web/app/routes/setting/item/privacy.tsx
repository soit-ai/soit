import { useTranslation } from '@/i18n'
import { useState } from 'react'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { toast } from '@/hooks/use-toast'
import { Shield, Lock, FileText, Cookie, Activity, Download, Trash2, AlertTriangle } from 'lucide-react'
function Page() {
  const { t } = useTranslation()
  const [dataCollection, setDataCollection] = useState(true)
  const [usageAnalytics, setUsageAnalytics] = useState(true)
  const [crashReports, setCrashReports] = useState(true)
  const [marketingEmails, setMarketingEmails] = useState(false)
  const [essentialCookies, setEssentialCookies] = useState(true)
  const [analyticsCookies, setAnalyticsCookies] = useState(true)
  const [marketingCookies, setMarketingCookies] = useState(false)
  const [thirdPartyCookies, setThirdPartyCookies] = useState(false)
  
  // 保存隐私设置
  const handleSavePrivacySettings = () => {
    // 这里应该有API调用来保存设置
    toast({
      title: '设置已保存',
      description: '您的隐私设置已更新',
    })
  }
  
  // 请求导出数据
  const handleRequestDataExport = () => {
    // 这里应该有API调用来请求数据导出
    toast({
      title: '请求已提交',
      description: '您的数据导出请求已提交，我们将在24小时内处理',
    })
  }
  
  // 请求删除数据
  const handleRequestDataDeletion = () => {
    // 这里应该有API调用来请求数据删除
    toast({
      title: '请求已提交',
      description: '您的数据删除请求已提交，我们将在7个工作日内处理',
      type: 'error'
    })
  }
  
  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold tracking-tight">隐私设置</h3>
          <p className="text-sm text-muted-foreground mt-1">管理您的数据和隐私偏好</p>
        </div>
        <Button onClick={handleSavePrivacySettings}>保存设置</Button>
      </div>

      <Tabs defaultValue="data" className="w-full">
        <TabsList className="mb-4 grid w-full max-w-md grid-cols-4">
          <TabsTrigger value="data">数据收集</TabsTrigger>
          <TabsTrigger value="cookies">Cookie 设置</TabsTrigger>
          <TabsTrigger value="policy">隐私政策</TabsTrigger>
          <TabsTrigger value="rights">数据权利</TabsTrigger>
        </TabsList>
        
        {/* 数据收集标签页 */}
        <TabsContent value="data">
          <Card>
            <CardHeader>
              <CardTitle>数据收集设置</CardTitle>
              <CardDescription>控制我们收集的数据类型</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>关于数据收集</AlertTitle>
                <AlertDescription>
                  更改这些设置可能会影响您的使用体验。某些基本数据对于服务正常运行是必要的。
                </AlertDescription>
              </Alert>
              
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label className="text-base">允许数据收集</Label>
                    <p className="text-sm text-muted-foreground">
                      允许我们收集基本的使用数据以改进服务
                    </p>
                  </div>
                  <Switch
                    checked={dataCollection}
                    onCheckedChange={setDataCollection}
                    disabled={true} // 基本数据收集不可禁用
                  />
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label className="text-base">使用统计</Label>
                    <p className="text-sm text-muted-foreground">
                      允许我们收集功能使用数据以改进用户体验
                    </p>
                  </div>
                  <Switch
                    checked={usageAnalytics}
                    onCheckedChange={setUsageAnalytics}
                  />
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label className="text-base">崩溃报告</Label>
                    <p className="text-sm text-muted-foreground">
                      自动发送崩溃报告以帮助我们修复问题
                    </p>
                  </div>
                  <Switch
                    checked={crashReports}
                    onCheckedChange={setCrashReports}
                  />
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label className="text-base">营销邮件</Label>
                    <p className="text-sm text-muted-foreground">
                      接收产品更新、优惠和营销信息
                    </p>
                  </div>
                  <Switch
                    checked={marketingEmails}
                    onCheckedChange={setMarketingEmails}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* Cookie 设置标签页 */}
        <TabsContent value="cookies">
          <Card>
            <CardHeader>
              <CardTitle>Cookie 设置</CardTitle>
              <CardDescription>管理网站使用的 Cookie</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label className="text-base">必要 Cookie</Label>
                    <p className="text-sm text-muted-foreground">
                      网站功能所必需的基本 Cookie，无法禁用
                    </p>
                  </div>
                  <Switch
                    checked={essentialCookies}
                    disabled={true}
                  />
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label className="text-base">分析 Cookie</Label>
                    <p className="text-sm text-muted-foreground">
                      帮助我们了解访问者如何使用网站
                    </p>
                  </div>
                  <Switch
                    checked={analyticsCookies}
                    onCheckedChange={setAnalyticsCookies}
                  />
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label className="text-base">营销 Cookie</Label>
                    <p className="text-sm text-muted-foreground">
                      用于跟踪访问者并显示个性化广告
                    </p>
                  </div>
                  <Switch
                    checked={marketingCookies}
                    onCheckedChange={setMarketingCookies}
                  />
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label className="text-base">第三方 Cookie</Label>
                    <p className="text-sm text-muted-foreground">
                      允许第三方服务在我们的网站上设置 Cookie
                    </p>
                  </div>
                  <Switch
                    checked={thirdPartyCookies}
                    onCheckedChange={setThirdPartyCookies}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* 隐私政策标签页 */}
        <TabsContent value="policy">
          <Card>
            <CardHeader>
              <CardTitle>隐私政策</CardTitle>
              <CardDescription>了解我们如何处理您的数据</CardDescription>
            </CardHeader>
            <CardContent>
              <Accordion type="single" collapsible className="w-full">
                <AccordionItem value="item-1">
                  <AccordionTrigger>数据收集</AccordionTrigger>
                  <AccordionContent>
                    <p className="text-sm text-muted-foreground">
                      我们收集的数据包括您的个人信息（如姓名、电子邮件地址）、设备信息（如IP地址、浏览器类型）以及使用数据（如功能使用情况、访问时间）。我们仅收集提供服务所必需的数据，并遵循数据最小化原则。
                    </p>
                  </AccordionContent>
                </AccordionItem>
                
                <AccordionItem value="item-2">
                  <AccordionTrigger>数据使用</AccordionTrigger>
                  <AccordionContent>
                    <p className="text-sm text-muted-foreground">
                      我们使用收集的数据来提供和改进我们的服务、个性化您的体验、进行分析和研究、与您沟通以及确保服务的安全性。我们不会将您的个人数据出售给第三方。
                    </p>
                  </AccordionContent>
                </AccordionItem>
                
                <AccordionItem value="item-3">
                  <AccordionTrigger>数据共享</AccordionTrigger>
                  <AccordionContent>
                    <p className="text-sm text-muted-foreground">
                      我们可能会与服务提供商、业务合作伙伴和关联公司共享您的数据，以便提供和改进我们的服务。我们要求所有第三方尊重您数据的安全性，并按照法律规定处理这些数据。
                    </p>
                  </AccordionContent>
                </AccordionItem>
                
                <AccordionItem value="item-4">
                  <AccordionTrigger>数据安全</AccordionTrigger>
                  <AccordionContent>
                    <p className="text-sm text-muted-foreground">
                      我们采取适当的技术和组织措施来保护您的个人数据，防止未经授权的访问、使用、泄露、修改或销毁。我们定期审查和更新我们的安全措施，以确保您的数据安全。
                    </p>
                  </AccordionContent>
                </AccordionItem>
                
                <AccordionItem value="item-5">
                  <AccordionTrigger>数据保留</AccordionTrigger>
                  <AccordionContent>
                    <p className="text-sm text-muted-foreground">
                      我们只在必要的时间内保留您的个人数据，以实现我们收集数据的目的，并遵守法律和监管要求。当数据不再需要时，我们会安全地删除或匿名化处理这些数据。
                    </p>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
              
              <div className="mt-6">
                <Button variant="outline" className="w-full">
                  <FileText className="mr-2 h-4 w-4" />
                  查看完整隐私政策
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* 数据权利标签页 */}
        <TabsContent value="rights">
          <Card>
            <CardHeader>
              <CardTitle>您的数据权利</CardTitle>
              <CardDescription>了解并行使您对个人数据的权利</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">访问权</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      您有权获取我们持有的关于您的个人数据的副本
                    </p>
                  </CardContent>
                </Card>
                
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">更正权</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      您有权要求更正我们持有的不准确或不完整的个人数据
                    </p>
                  </CardContent>
                </Card>
                
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">删除权</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      您有权在某些情况下要求删除您的个人数据
                    </p>
                  </CardContent>
                </Card>
                
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">限制处理权</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      您有权在某些情况下限制我们处理您的个人数据
                    </p>
                  </CardContent>
                </Card>
              </div>
              
              <div className="space-y-4">
                <Button className="w-full" onClick={handleRequestDataExport}>
                  <Download className="mr-2 h-4 w-4" />
                  请求导出我的数据
                </Button>
                
                <Button variant="destructive" className="w-full" onClick={handleRequestDataDeletion}>
                  <Trash2 className="mr-2 h-4 w-4" />
                  请求删除我的数据
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default Page
