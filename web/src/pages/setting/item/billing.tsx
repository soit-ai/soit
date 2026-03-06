import { useTranslation } from '@/i18n'
import { useState } from 'react'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { toast } from '@/hooks/use-toast'
import { CreditCard, Wallet, Receipt, History, Plus, Download, AlertCircle, CheckCircle2, Clock } from 'lucide-react'
function Page() {
  const { t } = useTranslation()
  
  // 订阅状态
  const [currentPlan, setCurrentPlan] = useState("free")
  const [billingCycle, setBillingCycle] = useState("monthly")
  
  // 支付方式状态
  const [paymentMethods, setPaymentMethods] = useState([
    { id: "card1", type: "card", last4: "4242", expiry: "12/25", isDefault: true },
    { id: "card2", type: "card", last4: "1234", expiry: "08/24", isDefault: false }
  ])
  
  // 升级订阅
  const handleUpgradeSubscription = () => {
    // 这里应该有API调用来升级订阅
    console.log('升级订阅到', currentPlan === 'free' ? 'pro' : 'enterprise')
    
    toast({
      title: '订阅升级请求已提交',
      description: '我们正在处理您的订阅升级请求',
    })
  }
  
  // 取消订阅
  const handleCancelSubscription = () => {
    // 这里应该有API调用来取消订阅
    console.log('取消订阅')
    
    toast({
      title: '订阅取消请求已提交',
      description: '您的订阅将在当前计费周期结束后取消',
      type: 'error'
    })
  }
  
  // 添加支付方式
  const handleAddPaymentMethod = () => {
    // 这里应该有API调用来添加支付方式
    console.log('添加支付方式')
    
    toast({
      title: '支付方式已添加',
      description: '您的新支付方式已成功添加',
    })
  }
  
  // 设置默认支付方式
  const handleSetDefaultPaymentMethod = (id: string) => {
    // 这里应该有API调用来设置默认支付方式
    console.log('设置默认支付方式', id)
    
    // 更新本地状态
    setPaymentMethods(paymentMethods.map(method => ({
      ...method,
      isDefault: method.id === id
    })))
    
    toast({
      title: '默认支付方式已更新',
      description: '您的默认支付方式已成功更新',
    })
  }
  
  // 删除支付方式
  const handleDeletePaymentMethod = (id: string) => {
    // 这里应该有API调用来删除支付方式
    console.log('删除支付方式', id)
    
    // 更新本地状态
    setPaymentMethods(paymentMethods.filter(method => method.id !== id))
    
    toast({
      title: '支付方式已删除',
      description: '您的支付方式已成功删除',
    })
  }
  
  // 下载发票
  const handleDownloadInvoice = (invoiceId: string) => {
    // 这里应该有API调用来下载发票
    console.log('下载发票', invoiceId)
    
    toast({
      title: '发票下载已开始',
      description: '您的发票正在下载中',
    })
  }
  
  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold tracking-tight">账单与订阅</h3>
          <p className="text-sm text-muted-foreground mt-1">管理您的订阅、支付方式和账单历史</p>
        </div>
      </div>

      <Tabs defaultValue="subscription" className="w-full">
        <TabsList className="mb-4 grid w-full max-w-md grid-cols-3">
          <TabsTrigger value="subscription">订阅管理</TabsTrigger>
          <TabsTrigger value="payment">支付方式</TabsTrigger>
          <TabsTrigger value="history">账单历史</TabsTrigger>
        </TabsList>
        
        {/* 订阅管理标签页 */}
        <TabsContent value="subscription">
          <Card>
            <CardHeader>
              <CardTitle>当前订阅</CardTitle>
              <CardDescription>管理您的订阅计划和计费周期</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="rounded-lg border p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-semibold">
                      {currentPlan === 'free' ? '免费版' : currentPlan === 'pro' ? '专业版' : '企业版'}
                      <Badge variant={currentPlan === 'free' ? 'outline' : 'default'} className="ml-2">
                        {currentPlan === 'free' ? '免费' : '活跃'}
                      </Badge>
                    </h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      {currentPlan === 'free' ? '基本功能访问' : currentPlan === 'pro' ? '全功能访问和优先支持' : '企业级功能和专属支持'}
                    </p>
                  </div>
                  {currentPlan !== 'free' && (
                    <div className="text-right">
                      <p className="text-lg font-semibold">
                        {currentPlan === 'pro' ? '$19.99' : '$49.99'}
                        <span className="text-sm text-muted-foreground">/{billingCycle === 'monthly' ? '月' : '年'}</span>
                      </p>
                      <p className="text-sm text-muted-foreground">
                        下次计费: 2025-07-01
                      </p>
                    </div>
                  )}
                </div>
                
                {currentPlan !== 'free' && (
                  <div className="mt-4 flex items-center">
                    <Label className="mr-4">计费周期:</Label>
                    <div className="flex items-center space-x-2">
                      <Button 
                        variant={billingCycle === 'monthly' ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setBillingCycle('monthly')}
                      >
                        月付
                      </Button>
                      <Button 
                        variant={billingCycle === 'yearly' ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setBillingCycle('yearly')}
                      >
                        年付 (节省 20%)
                      </Button>
                    </div>
                  </div>
                )}
              </div>
              
              <div className="grid gap-4 md:grid-cols-2">
                <Card className="border-dashed">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">免费版</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground mb-4">基本功能访问</p>
                    <ul className="text-sm space-y-2">
                      <li className="flex items-center">
                        <CheckCircle2 className="mr-2 h-4 w-4 text-green-500" />
                        每月 100 次请求
                      </li>
                      <li className="flex items-center">
                        <CheckCircle2 className="mr-2 h-4 w-4 text-green-500" />
                        标准模型访问
                      </li>
                      <li className="flex items-center">
                        <CheckCircle2 className="mr-2 h-4 w-4 text-green-500" />
                        社区支持
                      </li>
                    </ul>
                    {currentPlan !== 'free' ? (
                      <Button variant="outline" className="w-full mt-4" onClick={() => setCurrentPlan('free')}>
                        降级到免费版
                      </Button>
                    ) : (
                      <Button variant="outline" className="w-full mt-4" disabled>
                        当前计划
                      </Button>
                    )}
                  </CardContent>
                </Card>
                
                <Card className={currentPlan === 'pro' ? 'border-primary' : 'border-dashed'}>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">专业版</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground mb-4">全功能访问和优先支持</p>
                    <ul className="text-sm space-y-2">
                      <li className="flex items-center">
                        <CheckCircle2 className="mr-2 h-4 w-4 text-green-500" />
                        无限请求
                      </li>
                      <li className="flex items-center">
                        <CheckCircle2 className="mr-2 h-4 w-4 text-green-500" />
                        所有模型访问
                      </li>
                      <li className="flex items-center">
                        <CheckCircle2 className="mr-2 h-4 w-4 text-green-500" />
                        优先电子邮件支持
                      </li>
                    </ul>
                    {currentPlan === 'pro' ? (
                      <Button variant="outline" className="w-full mt-4" disabled>
                        当前计划
                      </Button>
                    ) : (
                      <Button className="w-full mt-4" onClick={() => setCurrentPlan('pro')}>
                        {currentPlan === 'free' ? '升级到专业版' : '降级到专业版'}
                      </Button>
                    )}
                  </CardContent>
                </Card>
              </div>
            </CardContent>
            <CardFooter className="flex justify-between">
              {currentPlan !== 'free' ? (
                <Button variant="destructive" onClick={handleCancelSubscription}>
                  取消订阅
                </Button>
              ) : (
                <div></div>
              )}
              <Button onClick={handleUpgradeSubscription} disabled={currentPlan === 'enterprise'}>
                {currentPlan === 'free' ? '升级订阅' : currentPlan === 'pro' ? '升级到企业版' : '管理订阅'}
              </Button>
            </CardFooter>
          </Card>
        </TabsContent>
        
        {/* 支付方式标签页 */}
        <TabsContent value="payment">
          <Card>
            <CardHeader>
              <CardTitle>支付方式</CardTitle>
              <CardDescription>管理您的付款方式</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {paymentMethods.map((method) => (
                <div key={method.id} className="flex items-center justify-between p-4 border rounded-lg">
                  <div className="flex items-center">
                    <CreditCard className="h-5 w-5 mr-3" />
                    <div>
                      <p className="font-medium">信用卡 •••• {method.last4}</p>
                      <p className="text-sm text-muted-foreground">到期日期: {method.expiry}</p>
                    </div>
                    {method.isDefault && (
                      <Badge variant="outline" className="ml-3">默认</Badge>
                    )}
                  </div>
                  <div className="flex gap-2">
                    {!method.isDefault && (
                      <Button variant="outline" size="sm" onClick={() => handleSetDefaultPaymentMethod(method.id)}>
                        设为默认
                      </Button>
                    )}
                    <Button variant="destructive" size="sm" onClick={() => handleDeletePaymentMethod(method.id)} disabled={method.isDefault && paymentMethods.length > 1}>
                      删除
                    </Button>
                  </div>
                </div>
              ))}
              
              <Button className="mt-4" onClick={handleAddPaymentMethod}>
                <Plus className="mr-2 h-4 w-4" />
                添加支付方式
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* 账单历史标签页 */}
        <TabsContent value="history">
          <Card>
            <CardHeader>
              <CardTitle>账单历史</CardTitle>
              <CardDescription>查看您的付款和发票历史</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="rounded-lg border">
                  <div className="flex items-center justify-between p-4">
                    <div>
                      <p className="font-medium">专业版订阅</p>
                      <p className="text-sm text-muted-foreground">交易日期: 2025-06-01</p>
                    </div>
                    <div className="text-right">
                      <p className="font-medium">$19.99</p>
                      <Badge variant="outline" className="ml-2">已支付</Badge>
                    </div>
                  </div>
                  <div className="border-t p-4 flex justify-between items-center">
                    <p className="text-sm text-muted-foreground">发票 #INV-2025-001</p>
                    <Button variant="ghost" size="sm" onClick={() => handleDownloadInvoice('INV-2025-001')}>
                      <Download className="mr-2 h-4 w-4" />
                      下载发票
                    </Button>
                  </div>
                </div>
                
                <div className="rounded-lg border">
                  <div className="flex items-center justify-between p-4">
                    <div>
                      <p className="font-medium">专业版订阅</p>
                      <p className="text-sm text-muted-foreground">交易日期: 2025-05-01</p>
                    </div>
                    <div className="text-right">
                      <p className="font-medium">$19.99</p>
                      <Badge variant="outline" className="ml-2">已支付</Badge>
                    </div>
                  </div>
                  <div className="border-t p-4 flex justify-between items-center">
                    <p className="text-sm text-muted-foreground">发票 #INV-2025-002</p>
                    <Button variant="ghost" size="sm" onClick={() => handleDownloadInvoice('INV-2025-002')}>
                      <Download className="mr-2 h-4 w-4" />
                      下载发票
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default Page
