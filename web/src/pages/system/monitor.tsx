import { useTranslation } from '@/i18n'
import { useState, useEffect, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Cpu, MemoryStick, HardDrive, Activity, RefreshCw, Server, Clock } from 'lucide-react'

// 导入监控组件
import {
  ServiceHealthCard,
  ResourceUsageCard,
  ServiceStatusTable,
  AlertList,
  MonitorChart,
  HeartbeatChart,
  MetricStatCard
} from '@/pages/system/ui/monitor'

// 导入数据生成器
import {
  generateSystemResources,
  generateServices,
  generateAlerts,
  generateHeartbeatData,
  generateChartOptions,
  generateSystemAvailability,
  generateServiceMetrics,
  generateAlertStats
} from '@/pages/system/ui/monitor/data-generator'

import type { Service } from '@/pages/system/ui/monitor/service-status-table'
import type { Alert } from '@/pages/system/ui/monitor/alert-list'
import type { HeartbeatData } from '@/pages/system/ui/monitor/heartbeat-chart'

function IndexPage() {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState('overview')
  const [refreshInterval, setRefreshInterval] = useState<string>('realtime')
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date())
  
  // 状态数据
  const [systemResources, setSystemResources] = useState(generateSystemResources())
  const [services, setServices] = useState<Service[]>(generateServices())
  const [alerts, setAlerts] = useState<Alert[]>(generateAlerts())
  const [heartbeatData, setHeartbeatData] = useState<HeartbeatData[]>(generateHeartbeatData())
  const [chartOptions, setChartOptions] = useState(generateChartOptions())
  const [systemAvailability, setSystemAvailability] = useState(generateSystemAvailability())
  const [serviceMetrics, setServiceMetrics] = useState(generateServiceMetrics())
  const [alertStats, setAlertStats] = useState(generateAlertStats(alerts))
  
  // 格式化日期
  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }
  
  // 刷新所有数据
  const refreshData = useCallback(() => {
    // 更新所有数据
    const newSystemResources = generateSystemResources()
    const newServices = generateServices()
    const newAlerts = generateAlerts()
    const newHeartbeatData = generateHeartbeatData()
    const newChartOptions = generateChartOptions()
    const newSystemAvailability = generateSystemAvailability()
    const newServiceMetrics = generateServiceMetrics()
    
    setSystemResources(newSystemResources)
    setServices(newServices)
    setAlerts(newAlerts)
    setHeartbeatData(newHeartbeatData)
    setChartOptions(newChartOptions)
    setSystemAvailability(newSystemAvailability)
    setServiceMetrics(newServiceMetrics)
    setAlertStats(generateAlertStats(newAlerts))
    setLastRefreshed(new Date())
  }, [])
  
  // 根据刷新间隔设置自动刷新
  useEffect(() => {
    let intervalId: NodeJS.Timeout | null = null
    
    if (refreshInterval !== 'manual') {
      const intervalMap: Record<string, number> = {
        'realtime': 5000,
        '30s': 30000,
        '1m': 60000,
        '5m': 300000
      }
      
      // 立即刷新一次
      refreshData()
      
      intervalId = setInterval(() => {
        refreshData()
      }, intervalMap[refreshInterval] || 60000)
    }
    
    return () => {
      if (intervalId) clearInterval(intervalId)
    }
  }, [refreshInterval, refreshData])

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold tracking-tight">系统监控</h3>
          <p className="text-muted-foreground">
            监控系统服务运行状态、性能指标和健康度
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-sm text-muted-foreground mr-2">
            最后更新: {lastRefreshed.toLocaleTimeString('zh-CN')}
          </div>
          <Button variant="outline" size="sm" onClick={refreshData}>
            <RefreshCw className="mr-2 h-4 w-4" />
            刷新数据
          </Button>
          <Select value={refreshInterval} onValueChange={setRefreshInterval}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="数据更新频率" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="realtime">实时更新 (5秒)</SelectItem>
              <SelectItem value="30s">每30秒</SelectItem>
              <SelectItem value="1m">每分钟</SelectItem>
              <SelectItem value="5m">每5分钟</SelectItem>
              <SelectItem value="manual">手动刷新</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full max-w-md grid-cols-3">
          <TabsTrigger value="overview">系统概览</TabsTrigger>
          <TabsTrigger value="services">服务监控</TabsTrigger>
          <TabsTrigger value="alerts">告警管理</TabsTrigger>
        </TabsList>
        
        <TabsContent value="overview" className="mt-6 space-y-6">
          {/* 系统健康状态概览 */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <ServiceHealthCard
              status="healthy"
              name="系统可用性"
              value={systemAvailability.current}
              icon={<Activity className="h-4 w-4 text-muted-foreground" />}
              description={`过去24小时: ${systemAvailability.last24h}`}
            />
            <ResourceUsageCard
              title="CPU使用率"
              icon={<Cpu className="h-4 w-4" />}
              usagePercentage={systemResources.cpu.usage}
              details={[
                { label: '核心数', value: `${systemResources.cpu.cores}` },
                { label: '温度', value: `${systemResources.cpu.temperature}°C` }
              ]}
            />
            <ResourceUsageCard
              title="内存使用率"
              icon={<MemoryStick className="h-4 w-4" />}
              usagePercentage={systemResources.memory.usage}
              details={[
                { label: '已用', value: `${systemResources.memory.used}GB` },
                { label: '总量', value: `${systemResources.memory.total}GB` }
              ]}
            />
            <ResourceUsageCard
              title="磁盘使用率"
              icon={<HardDrive className="h-4 w-4" />}
              usagePercentage={systemResources.disk.usage}
              details={[
                { label: '已用', value: `${systemResources.disk.used}GB` },
                { label: '总量', value: `${systemResources.disk.total}GB` }
              ]}
            />
          </div>
          
          {/* 性能指标图表 */}
          <div className="grid gap-4 md:grid-cols-2 h-auto">
            <MonitorChart
              title="响应时间趋势"
              description="各服务响应时间变化趋势"
              options={chartOptions.responseTimeChartOptions}
              className="h-100"
            />
            <MonitorChart
              title="系统负载趋势"
              description="CPU、内存和磁盘I/O使用率"
              options={chartOptions.systemLoadChartOptions}
              className="h-100"
            />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <MonitorChart
              title="请求量统计"
              description="系统请求成功与失败数量"
              options={chartOptions.requestCountChartOptions}
              className="h-100"
            />
            <MonitorChart
              title="错误率监控"
              description="系统错误率变化趋势及警告阈值"
              options={chartOptions.errorRateChartOptions}
              className="h-100"
            />
          </div>
        </TabsContent>
        
        <TabsContent value="services" className="mt-6 space-y-6">
          {/* 服务健康状态表格 */}
          <Card>
            <CardHeader>
              <CardTitle>服务健康状态</CardTitle>
              <CardDescription>
                所有关键服务的当前运行状态和可用性
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ServiceStatusTable services={services} />
            </CardContent>
          </Card>
          
          {/* 服务心跳图 */}
          <HeartbeatChart
            title="服务心跳监控"
            data={heartbeatData}
            description="过去24小时的服务可用性状态"
          />
          
          {/* 关键指标 */}
          <div className="grid gap-4 md:grid-cols-3">
            <MetricStatCard
              title="API请求量"
              value={serviceMetrics.apiRequests}
              icon={<Activity className="h-4 w-4" />}
              change={serviceMetrics.apiRequestsChange}
            />
            <MetricStatCard
              title="平均响应时间"
              value={serviceMetrics.avgResponseTime}
              icon={<Clock className="h-4 w-4" />}
              change={serviceMetrics.avgResponseTimeChange}
            />
            <MetricStatCard
              title="错误率"
              value={serviceMetrics.errorRate}
              icon={<Server className="h-4 w-4" />}
              change={serviceMetrics.errorRateChange}
            />
          </div>
        </TabsContent>
        
        <TabsContent value="alerts" className="mt-6 space-y-6">
          {/* 告警统计卡片 */}
          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">活跃告警</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {alerts.filter(alert => alert.status === 'active').length}
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  当前需要处理的告警数量
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">严重告警</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {alerts.filter(alert => alert.severity === 'critical' && alert.status === 'active').length}
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  需要立即处理的严重告警
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">已解决告警</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {alerts.filter(alert => alert.status === 'resolved').length}
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  过去24小时内已解决的告警
                </p>
              </CardContent>
            </Card>
          </div>
          
          {/* 告警列表 */}
          <Card>
            <CardHeader>
              <CardTitle>系统告警</CardTitle>
              <CardDescription>
                当前活跃的系统告警及其状态
              </CardDescription>
            </CardHeader>
            <CardContent>
              <AlertList alerts={alerts} formatDate={formatDate} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default IndexPage
