import { useTranslation } from '@/i18n'
import { useState } from 'react'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { toast } from '@/hooks/use-toast'
import { BarChart3, PieChart, LineChart, Settings, Download, RefreshCw, Clock, Calendar, CheckCircle2, Filter } from 'lucide-react'
function Page() {
  const { t } = useTranslation()
  
  // 数据收集设置
  const [usageAnalytics, setUsageAnalytics] = useState(true)
  const [featureUsage, setFeatureUsage] = useState(true)
  const [performanceMetrics, setPerformanceMetrics] = useState(true)
  const [errorReporting, setErrorReporting] = useState(true)
  const [userJourney, setUserJourney] = useState(false)
  
  // 报告设置
  const [defaultTimeRange, setDefaultTimeRange] = useState("week")
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [defaultChartType, setDefaultChartType] = useState("bar")
  const [emailReports, setEmailReports] = useState(false)
  const [reportFrequency, setReportFrequency] = useState("weekly")
  
  // 保存分析设置
  const handleSaveAnalyticsSettings = () => {
    // 这里应该有API调用来保存设置
    toast({
      title: '设置已保存',
      description: '您的数据分析偏好已更新',
    })
  }
  
  // 导出分析数据
  const handleExportAnalytics = () => {
    // 这里应该有API调用来导出数据
    toast({
      title: '数据导出已开始',
      description: '您的分析数据正在准备中，完成后将通知您',
    })
  }
  
  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold tracking-tight">数据分析设置</h3>
          <p className="text-sm text-muted-foreground mt-1">管理您的数据分析偏好和报告设置</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleExportAnalytics}>
            <Download className="mr-2 h-4 w-4" />
            导出数据
          </Button>
          <Button onClick={handleSaveAnalyticsSettings}>保存设置</Button>
        </div>
      </div>

      <Tabs defaultValue="collection" className="w-full">
        <TabsList className="mb-4 grid w-full max-w-md grid-cols-3">
          <TabsTrigger value="collection">数据收集</TabsTrigger>
          <TabsTrigger value="visualization">可视化偏好</TabsTrigger>
          <TabsTrigger value="reports">报告设置</TabsTrigger>
        </TabsList>
        
        {/* 数据收集标签页 */}
        <TabsContent value="collection">
          <Card>
            <CardHeader>
              <CardTitle>数据收集设置</CardTitle>
              <CardDescription>控制我们收集的分析数据类型</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-base">使用统计</Label>
                  <p className="text-sm text-muted-foreground">
                    收集基本使用数据，如页面访问和会话时长
                  </p>
                </div>
                <Switch
                  checked={usageAnalytics}
                  onCheckedChange={setUsageAnalytics}
                />
              </div>
              
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-base">功能使用情况</Label>
                  <p className="text-sm text-muted-foreground">
                    跟踪各功能的使用频率和方式
                  </p>
                </div>
                <Switch
                  checked={featureUsage}
                  onCheckedChange={setFeatureUsage}
                />
              </div>
              
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-base">性能指标</Label>
                  <p className="text-sm text-muted-foreground">
                    收集应用性能数据，如加载时间和响应速度
                  </p>
                </div>
                <Switch
                  checked={performanceMetrics}
                  onCheckedChange={setPerformanceMetrics}
                />
              </div>
              
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-base">错误报告</Label>
                  <p className="text-sm text-muted-foreground">
                    自动收集应用错误和崩溃信息
                  </p>
                </div>
                <Switch
                  checked={errorReporting}
                  onCheckedChange={setErrorReporting}
                />
              </div>
              
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-base">用户旅程分析</Label>
                  <p className="text-sm text-muted-foreground">
                    跟踪用户在应用中的完整路径和行为模式
                  </p>
                </div>
                <Switch
                  checked={userJourney}
                  onCheckedChange={setUserJourney}
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* 可视化偏好标签页 */}
        <TabsContent value="visualization">
          <Card>
            <CardHeader>
              <CardTitle>可视化偏好</CardTitle>
              <CardDescription>自定义您的数据可视化选项</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label className="text-base">默认图表类型</Label>
                <Select value={defaultChartType} onValueChange={setDefaultChartType}>
                  <SelectTrigger className="w-full md:w-[250px]">
                    <SelectValue placeholder="选择图表类型" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="bar">
                      <div className="flex items-center">
                        <BarChart3 className="mr-2 h-4 w-4" />
                        柱状图
                      </div>
                    </SelectItem>
                    <SelectItem value="line">
                      <div className="flex items-center">
                        <LineChart className="mr-2 h-4 w-4" />
                        折线图
                      </div>
                    </SelectItem>
                    <SelectItem value="pie">
                      <div className="flex items-center">
                        <PieChart className="mr-2 h-4 w-4" />
                        饼图
                      </div>
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <div className="space-y-2">
                <Label className="text-base">默认时间范围</Label>
                <Select value={defaultTimeRange} onValueChange={setDefaultTimeRange}>
                  <SelectTrigger className="w-full md:w-[250px]">
                    <SelectValue placeholder="选择时间范围" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="day">今天</SelectItem>
                    <SelectItem value="week">本周</SelectItem>
                    <SelectItem value="month">本月</SelectItem>
                    <SelectItem value="quarter">本季度</SelectItem>
                    <SelectItem value="year">本年</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-base">自动刷新数据</Label>
                  <p className="text-sm text-muted-foreground">
                    自动刷新仪表盘和图表数据
                  </p>
                </div>
                <Switch
                  checked={autoRefresh}
                  onCheckedChange={setAutoRefresh}
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* 报告设置标签页 */}
        <TabsContent value="reports">
          <Card>
            <CardHeader>
              <CardTitle>报告设置</CardTitle>
              <CardDescription>管理您的分析报告偏好</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-base">电子邮件报告</Label>
                  <p className="text-sm text-muted-foreground">
                    定期接收数据分析报告的电子邮件
                  </p>
                </div>
                <Switch
                  checked={emailReports}
                  onCheckedChange={setEmailReports}
                />
              </div>
              
              {emailReports && (
                <div className="space-y-2 ml-6">
                  <Label className="text-base">报告频率</Label>
                  <Select value={reportFrequency} onValueChange={setReportFrequency}>
                    <SelectTrigger className="w-full md:w-[250px]">
                      <SelectValue placeholder="选择频率" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="daily">
                        <div className="flex items-center">
                          <Clock className="mr-2 h-4 w-4" />
                          每日
                        </div>
                      </SelectItem>
                      <SelectItem value="weekly">
                        <div className="flex items-center">
                          <Calendar className="mr-2 h-4 w-4" />
                          每周
                        </div>
                      </SelectItem>
                      <SelectItem value="monthly">
                        <div className="flex items-center">
                          <Calendar className="mr-2 h-4 w-4" />
                          每月
                        </div>
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}
              
              <div className="pt-4">
                <Button variant="outline" className="w-full">
                  <Filter className="mr-2 h-4 w-4" />
                  自定义报告内容
                </Button>
              </div>
            </CardContent>
            <CardFooter className="flex justify-between">
              <Button variant="outline">
                <Settings className="mr-2 h-4 w-4" />
                重置为默认设置
              </Button>
              <Button onClick={handleSaveAnalyticsSettings}>
                <CheckCircle2 className="mr-2 h-4 w-4" />
                保存偏好
              </Button>
            </CardFooter>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default Page
