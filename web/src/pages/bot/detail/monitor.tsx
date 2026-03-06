import { useTranslation } from '@/i18n'
import { useState, useEffect } from 'react'
import { useParams } from 'react-router'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { MessageSquare, Users, Clock, Cpu, Calendar, RefreshCw, Download } from 'lucide-react'

import {
  PageHeader,
  StatCard,
  UserActivityChart,
  EfficiencyMetrics,
  ResponseTimeChart,
  ResourceUsage,
  AnomalyMonitor,
  TokenUsageChart,
  UsageDistribution,
  UserStatsTable
} from './ui/monitor'
import { useNavLayout } from '@/components/layout/nav-layout'

function Page() {
  const { t } = useTranslation()
  const { id } = useParams()
  const [activeTab, setActiveTab] = useState('overview')
  const [timeRange, setTimeRange] = useState('7d')
  const [isLoading, setIsLoading] = useState(false)
  const { setHeaderContent } = useNavLayout()

  useEffect(() => {
    setHeaderContent(
      <PageHeader
        title={t('bot.monitor.title')}
        timeRange={timeRange}
        onTimeRangeChange={setTimeRange}
        onRefresh={loadData}
      />
    )
    return () => setHeaderContent(null)
  }, [setHeaderContent, t, timeRange])
  
  const [overviewData, setOverviewData] = useState({
    totalConversations: 1254,
    activeUsers: 87,
    avgResponseTime: 1.8,
    completionRate: '98.5%',
    tokensUsed: 1458923,
    dailyActiveUsers: [45, 52, 49, 62, 58, 75, 87],
    responseTimeData: [2.1, 1.9, 2.0, 1.8, 1.7, 1.8, 1.8],
    usageByDay: [12500, 15800, 14200, 18500, 16700, 19800, 22400],
  })
  
  useEffect(() => {
    loadData()
  }, [timeRange])
  
  const loadData = () => {
    setIsLoading(true)
    
    setTimeout(() => {
      setIsLoading(false)
    }, 500)
  }
  
  const statCards = [
    {
      title: t('bot.monitor.stat.totalConversations'),
      value: overviewData.totalConversations,
      icon: <MessageSquare className="h-6 w-6 text-primary" />,
      iconBgClass: 'bg-primary/10',
      iconClass: 'text-primary',
      trend: {
        value: '+12.5%',
        isPositive: true,
        label: t('bot.monitor.trend.sinceLastWeek'),
      }
    },
    {
      title: t('bot.monitor.stat.activeUsers'),
      value: overviewData.activeUsers,
      icon: <Users className="h-6 w-6 text-blue-500" />,
      iconBgClass: 'bg-blue-100',
      iconClass: 'text-blue-500',
      trend: {
        value: '+8.3%',
        isPositive: true,
        label: t('bot.monitor.trend.sinceLastWeek'),
      }
    },
    {
      title: t('bot.monitor.stat.avgResponseTime'),
      value: t('bot.monitor.units.seconds', { value: overviewData.avgResponseTime.toFixed(1) }),
      icon: <Clock className="h-6 w-6 text-yellow-500" />,
      iconBgClass: 'bg-yellow-100',
      iconClass: 'text-yellow-500',
      trend: {
        value: t('bot.monitor.units.seconds', { value: -0.2 }),
        isPositive: true,
        label: t('bot.monitor.trend.sinceLastWeek'),
      }
    },
    {
      title: t('bot.monitor.stat.tokenUsage'),
      value: t('bot.monitor.units.tokensK', { value: (overviewData.tokensUsed / 1000).toFixed(1) }),
      icon: <Cpu className="h-6 w-6 text-purple-500" />,
      iconBgClass: 'bg-purple-100',
      iconClass: 'text-purple-500',
      trend: {
        value: '+15.2%',
        isPositive: true,
        label: t('bot.monitor.trend.sinceLastWeek'),
      }
    }
  ]
  
  const efficiencyMetrics = [
    {
      name: t('bot.monitor.efficiency.completionRate'),
      description: t('bot.monitor.efficiency.completionRateDesc'),
      value: overviewData.completionRate
    },
    {
      name: t('bot.monitor.efficiency.knowledgeHitRate'),
      description: t('bot.monitor.efficiency.knowledgeHitRateDesc'),
      value: '76.2%'
    },
    {
      name: t('bot.monitor.efficiency.userSatisfaction'),
      description: t('bot.monitor.efficiency.userSatisfactionDesc'),
      value: '92.8%'
    },
    {
      name: t('bot.monitor.efficiency.systemAvailability'),
      description: t('bot.monitor.efficiency.systemAvailabilityDesc'),
      value: '99.95%'
    }
  ]
  
  const resourceUsage = [
    {
      name: t('bot.monitor.resources.cpu'),
      description: t('bot.monitor.resources.cpuDesc'),
      value: 32
    },
    {
      name: t('bot.monitor.resources.memory'),
      description: t('bot.monitor.resources.memoryDesc'),
      value: 45
    },
    {
      name: t('bot.monitor.resources.network'),
      description: t('bot.monitor.resources.networkDesc'),
      value: 28
    },
    {
      name: t('bot.monitor.resources.storage'),
      description: t('bot.monitor.resources.storageDesc'),
      value: 52
    }
  ]
  
  const anomalies = [
    {
      title: t('bot.monitor.anomalies.items.responseTimeoutTitle'),
      severity: 'critical',
      description: t('bot.monitor.anomalies.items.responseTimeoutDesc'),
      timestamp: t('bot.monitor.anomalies.time.today', { time: '09:45:12' }),
      icon: 'activity'
    },
    {
      title: t('bot.monitor.anomalies.items.cpuHighTitle'),
      severity: 'warning',
      description: t('bot.monitor.anomalies.items.cpuHighDesc'),
      timestamp: t('bot.monitor.anomalies.time.yesterday', { time: '18:30:45' }),
      icon: 'cpu'
    },
    {
      title: t('bot.monitor.anomalies.items.peakConcurrencyTitle'),
      severity: 'info',
      description: t('bot.monitor.anomalies.items.peakConcurrencyDesc'),
      timestamp: t('bot.monitor.anomalies.time.daysAgo', { count: 2, time: '14:15:32' }),
      icon: 'users'
    },
    {
      title: t('bot.monitor.anomalies.items.autoRecoveryTitle'),
      severity: 'success',
      description: t('bot.monitor.anomalies.items.autoRecoveryDesc'),
      timestamp: t('bot.monitor.anomalies.time.daysAgo', { count: 2, time: '02:10:05' }),
      icon: 'refresh'
    }
  ]
  
  const usageDistribution = [
    {
      name: t('bot.monitor.usageDistribution.items.chat'),
      value: 65,
      color: 'bg-primary'
    },
    {
      name: t('bot.monitor.usageDistribution.items.knowledge'),
      value: 20,
      color: 'bg-blue-500'
    },
    {
      name: t('bot.monitor.usageDistribution.items.tools'),
      value: 10,
      color: 'bg-green-500'
    },
    {
      name: t('bot.monitor.usageDistribution.items.systemPrompt'),
      value: 5,
      color: 'bg-yellow-500'
    }
  ]
  
  const userGroups = [
    {
      name: t('bot.monitor.userStats.groups.new'),
      iconColor: 'text-blue-500',
      userCount: 32,
      sessionCount: 128,
      avgSessionDuration: t('bot.monitor.units.minutes', { value: 4 }),
      tokenUsage: '245K',
      satisfaction: 85
    },
    {
      name: t('bot.monitor.userStats.groups.active'),
      iconColor: 'text-purple-500',
      userCount: 45,
      sessionCount: 892,
      avgSessionDuration: t('bot.monitor.units.minutes', { value: 8 }),
      tokenUsage: '980K',
      satisfaction: 94
    },
    {
      name: t('bot.monitor.userStats.groups.enterprise'),
      iconColor: 'text-yellow-500',
      userCount: 10,
      sessionCount: 234,
      avgSessionDuration: t('bot.monitor.units.minutes', { value: 12 }),
      tokenUsage: '234K',
      satisfaction: 92
    },
    {
      name: t('bot.monitor.userStats.groups.test'),
      iconColor: 'text-red-500',
      userCount: 5,
      sessionCount: 78,
      avgSessionDuration: t('bot.monitor.units.minutes', { value: 3 }),
      tokenUsage: '45K',
      satisfaction: 78
    }
  ]
  
  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      
      <Tabs defaultValue="overview" value={activeTab} onValueChange={setActiveTab} className="w-full">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-4">
          <TabsList className="w-full md:w-auto grid grid-cols-3 md:flex">
            <TabsTrigger value="overview">{t('bot.monitor.tabs.overview')}</TabsTrigger>
            <TabsTrigger value="performance">{t('bot.monitor.tabs.performance')}</TabsTrigger>
            <TabsTrigger value="usage">{t('bot.monitor.tabs.usage')}</TabsTrigger>
          </TabsList>
          
          <div className="flex items-center gap-2 w-full md:w-auto">
            <Select value={timeRange} onValueChange={setTimeRange}>
              <SelectTrigger className="w-[150px]">
                <Calendar className="h-4 w-4 mr-2" />
                <SelectValue placeholder={t('bot.monitor.timeRange.placeholder')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="24h">{t('bot.monitor.timeRange.last24h')}</SelectItem>
                <SelectItem value="7d">{t('bot.monitor.timeRange.last7d')}</SelectItem>
                <SelectItem value="30d">{t('bot.monitor.timeRange.last30d')}</SelectItem>
                <SelectItem value="90d">{t('bot.monitor.timeRange.last90d')}</SelectItem>
              </SelectContent>
            </Select>
            
            <Button variant="outline" size="sm" onClick={loadData}>
              <RefreshCw className="h-4 w-4 mr-1" />
              {t('bot.monitor.actions.refresh')}
            </Button>
            <Button variant="outline" size="sm">
              <Download className="h-4 w-4 mr-1" />
              {t('bot.monitor.actions.export')}
            </Button>
          </div>
        </div>
        
        <TabsContent value="overview" className="mt-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
            {statCards.map((card, index) => (
              <StatCard key={index} {...card} />
            ))}
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <UserActivityChart dailyActiveUsers={overviewData.dailyActiveUsers} />
            <EfficiencyMetrics metrics={efficiencyMetrics} />
          </div>
        </TabsContent>
        
        <TabsContent value="performance" className="mt-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <ResponseTimeChart 
              responseTimeData={overviewData.responseTimeData} 
              avgResponseTime={overviewData.avgResponseTime} 
            />
            <ResourceUsage resources={resourceUsage} />
          </div>
          
          <AnomalyMonitor 
            anomalies={anomalies} 
            summary={{ total: 4, critical: 1 }} 
          />
        </TabsContent>
        
        <TabsContent value="usage" className="mt-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <TokenUsageChart 
              usageByDay={overviewData.usageByDay} 
              totalTokens={overviewData.tokensUsed} 
            />
            <UsageDistribution usageItems={usageDistribution} />
          </div>
          
          <div className="grid grid-cols-1 gap-4">
            <UserStatsTable 
              userGroups={userGroups} 
              summary={{ totalUsers: 92, totalSessions: 1332 }} 
            />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default Page
