import type { Service } from './service-status-table'
import type { Alert } from './alert-list'
import type { HeartbeatData } from './heartbeat-chart'

// 基础系统资源数据
const baseSystemResources = {
  cpu: {
    usage: 42,
    cores: 8,
    temperature: 65
  },
  memory: {
    used: 12.4,
    total: 32,
    usage: 38.75
  },
  disk: {
    used: 256,
    total: 1024,
    usage: 25
  },
  network: {
    incoming: 25.6,
    outgoing: 12.8,
    totalRequests: 1250
  }
}

// 基础服务数据
const baseServices: Service[] = [
  {
    id: 'srv-001',
    name: 'API服务',
    status: 'healthy',
    uptime: '99.98%',
    responseTime: '120ms',
    lastChecked: new Date().toISOString()
  },
  {
    id: 'srv-002',
    name: '数据库服务',
    status: 'healthy',
    uptime: '99.95%',
    responseTime: '45ms',
    lastChecked: new Date().toISOString()
  },
  {
    id: 'srv-003',
    name: '认证服务',
    status: 'warning',
    uptime: '99.5%',
    responseTime: '350ms',
    lastChecked: new Date().toISOString()
  },
  {
    id: 'srv-004',
    name: '存储服务',
    status: 'healthy',
    uptime: '99.99%',
    responseTime: '85ms',
    lastChecked: new Date().toISOString()
  },
  {
    id: 'srv-005',
    name: '消息队列',
    status: 'critical',
    uptime: '95.2%',
    responseTime: '520ms',
    lastChecked: new Date().toISOString()
  }
]

// 基础告警数据
const baseAlerts: Alert[] = [
  {
    id: 'alert-001',
    service: '消息队列',
    severity: 'critical',
    message: '服务响应时间超过阈值',
    timestamp: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
    status: 'active'
  },
  {
    id: 'alert-002',
    service: '认证服务',
    severity: 'warning',
    message: '内存使用率超过80%',
    timestamp: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    status: 'active'
  },
  {
    id: 'alert-003',
    service: 'API服务',
    severity: 'info',
    message: '服务重启成功',
    timestamp: new Date(Date.now() - 135 * 60 * 1000).toISOString(),
    status: 'resolved'
  },
  {
    id: 'alert-004',
    service: '数据库服务',
    severity: 'warning',
    message: '数据库连接池接近上限',
    timestamp: new Date(Date.now() - 180 * 60 * 1000).toISOString(),
    status: 'resolved'
  },
  {
    id: 'alert-005',
    service: '存储服务',
    severity: 'info',
    message: '存储空间清理完成',
    timestamp: new Date(Date.now() - 240 * 60 * 1000).toISOString(),
    status: 'resolved'
  }
]

// 生成随机波动值
const getRandomFluctuation = (baseValue: number, maxFluctuation: number): number => {
  const fluctuation = (Math.random() - 0.5) * 2 * maxFluctuation
  return Math.max(0, baseValue + fluctuation)
}

// 随机改变状态
const getRandomStatus = (currentStatus: 'healthy' | 'warning' | 'critical', changeProb: number = 0.1): 'healthy' | 'warning' | 'critical' => {
  if (Math.random() > changeProb) return currentStatus
  
  const statuses: ('healthy' | 'warning' | 'critical')[] = ['healthy', 'warning', 'critical']
  const currentIndex = statuses.indexOf(currentStatus)
  const possibleStatuses = statuses.filter((_, index) => index !== currentIndex)
  
  return possibleStatuses[Math.floor(Math.random() * possibleStatuses.length)]
}

// 生成动态系统资源数据
export const generateSystemResources = () => {
  return {
    cpu: {
      usage: Math.min(100, getRandomFluctuation(baseSystemResources.cpu.usage, 15)),
      cores: baseSystemResources.cpu.cores,
      temperature: getRandomFluctuation(baseSystemResources.cpu.temperature, 5)
    },
    memory: {
      used: getRandomFluctuation(baseSystemResources.memory.used, 2),
      total: baseSystemResources.memory.total,
      usage: Math.min(100, getRandomFluctuation(baseSystemResources.memory.usage, 10))
    },
    disk: {
      used: getRandomFluctuation(baseSystemResources.disk.used, 10),
      total: baseSystemResources.disk.total,
      usage: Math.min(100, getRandomFluctuation(baseSystemResources.disk.usage, 5))
    },
    network: {
      incoming: getRandomFluctuation(baseSystemResources.network.incoming, 8),
      outgoing: getRandomFluctuation(baseSystemResources.network.outgoing, 5),
      totalRequests: Math.round(getRandomFluctuation(baseSystemResources.network.totalRequests, 200))
    }
  }
}

// 生成动态服务数据
export const generateServices = (): Service[] => {
  return baseServices.map(service => {
    const newStatus = getRandomStatus(service.status as 'healthy' | 'warning' | 'critical')
    const responseTimeBase = parseInt(service.responseTime, 10)
    const newResponseTime = Math.round(getRandomFluctuation(responseTimeBase, responseTimeBase * 0.3))
    
    // 根据状态调整可用性
    let uptime = service.uptime
    if (newStatus === 'warning') {
      uptime = `${(99 + Math.random() * 0.9).toFixed(2)}%`
    } else if (newStatus === 'critical') {
      uptime = `${(95 + Math.random() * 4).toFixed(2)}%`
    } else {
      uptime = `${(99.9 + Math.random() * 0.09).toFixed(2)}%`
    }
    
    return {
      ...service,
      status: newStatus,
      uptime,
      responseTime: `${newResponseTime}ms`,
      lastChecked: new Date().toISOString()
    }
  })
}

// 生成动态告警数据
export const generateAlerts = (): Alert[] => {
  // 有概率添加新告警
  const alerts = [...baseAlerts]
  
  if (Math.random() < 0.2) {
    const services = ['API服务', '数据库服务', '认证服务', '存储服务', '消息队列']
    const severities: ('critical' | 'warning' | 'info')[] = ['critical', 'warning', 'info']
    const messages = [
      '服务响应时间超过阈值',
      'CPU使用率过高',
      '内存使用率过高',
      '磁盘空间不足',
      '连接数超过限制',
      '服务重启',
      '数据同步失败'
    ]
    
    alerts.push({
      id: `alert-${Date.now()}`,
      service: services[Math.floor(Math.random() * services.length)],
      severity: severities[Math.floor(Math.random() * severities.length)],
      message: messages[Math.floor(Math.random() * messages.length)],
      timestamp: new Date().toISOString(),
      status: 'active'
    })
  }
  
  // 有概率解决现有告警
  return alerts.map(alert => {
    if (alert.status === 'active' && Math.random() < 0.1) {
      return { ...alert, status: 'resolved' }
    }
    return alert
  })
}

// 生成心跳数据
export const generateHeartbeatData = (): HeartbeatData[] => {
  const services = ['API服务', '数据库服务', '认证服务', '存储服务', '消息队列']
  
  return services.map(service => {
    // 为每个服务生成24小时的心跳数据
    const timestamps = Array.from({ length: 24 }, (_, i) => {
      const time = new Date()
      time.setHours(time.getHours() - (24 - i))
      return time.toISOString()
    })
    
    // 生成状态数据，大部分是成功的
    const status: ('success' | 'failure' | 'warning')[] = timestamps.map(() => {
      const rand = Math.random()
      if (rand > 0.9) return 'failure'
      if (rand > 0.8) return 'warning'
      return 'success'
    })
    
    return { service, timestamps, status }
  })
}

// 生成图表数据
export const generateChartOptions = () => {
  // 生成时间序列数据
  const generateTimeSeriesData = (hours: number, baseValue: number, volatility: number) => {
    const now = new Date()
    return Array.from({ length: hours }, (_, i) => {
      const time = new Date(now.getTime() - (hours - i) * 60 * 60 * 1000)
      const value = baseValue + (Math.random() - 0.5) * volatility
      return [
        time.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }), 
        Math.max(0, Number(value.toFixed(2)))
      ]
    })
  }

  // 响应时间图表数据
  const responseTimeChartOptions = {
    title: {
      text: '服务响应时间趋势'
    },
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: ['API服务', '数据库服务', '认证服务', '存储服务', '消息队列']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: generateTimeSeriesData(12, 0, 0).map(item => item[0])
    },
    yAxis: {
      type: 'value',
      name: '响应时间(ms)'
    },
    series: [
      {
        name: 'API服务',
        type: 'line',
        data: generateTimeSeriesData(12, 120, 50).map(item => item[1])
      },
      {
        name: '数据库服务',
        type: 'line',
        data: generateTimeSeriesData(12, 45, 20).map(item => item[1])
      },
      {
        name: '认证服务',
        type: 'line',
        data: generateTimeSeriesData(12, 350, 100).map(item => item[1])
      },
      {
        name: '存储服务',
        type: 'line',
        data: generateTimeSeriesData(12, 85, 30).map(item => item[1])
      },
      {
        name: '消息队列',
        type: 'line',
        data: generateTimeSeriesData(12, 520, 150).map(item => item[1])
      }
    ]
  }

  // 系统负载图表数据
  const systemLoadChartOptions = {
    title: {
      text: '系统负载趋势'
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        label: {
          backgroundColor: '#6a7985'
        }
      }
    },
    legend: {
      data: ['CPU使用率', '内存使用率', '磁盘I/O']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: generateTimeSeriesData(12, 0, 0).map(item => item[0])
    },
    yAxis: {
      type: 'value',
      name: '使用率(%)'
    },
    series: [
      {
        name: 'CPU使用率',
        type: 'line',
        areaStyle: {},
        emphasis: {
          focus: 'series'
        },
        data: generateTimeSeriesData(12, 42, 20).map(item => item[1])
      },
      {
        name: '内存使用率',
        type: 'line',
        areaStyle: {},
        emphasis: {
          focus: 'series'
        },
        data: generateTimeSeriesData(12, 38, 15).map(item => item[1])
      },
      {
        name: '磁盘I/O',
        type: 'line',
        areaStyle: {},
        emphasis: {
          focus: 'series'
        },
        data: generateTimeSeriesData(12, 25, 10).map(item => item[1])
      }
    ]
  }

  // 请求量统计图表数据
  const requestCountChartOptions = {
    title: {
      text: '系统请求量统计'
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
    },
    legend: {
      data: ['成功请求', '失败请求']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: generateTimeSeriesData(12, 0, 0).map(item => item[0])
    },
    yAxis: {
      type: 'value',
      name: '请求数'
    },
    series: [
      {
        name: '成功请求',
        type: 'bar',
        stack: 'total',
        emphasis: {
          focus: 'series'
        },
        data: generateTimeSeriesData(12, 1200, 500).map(item => item[1])
      },
      {
        name: '失败请求',
        type: 'bar',
        stack: 'total',
        emphasis: {
          focus: 'series'
        },
        data: generateTimeSeriesData(12, 50, 30).map(item => item[1])
      }
    ]
  }

  // 错误率监控图表数据
  const errorRateChartOptions = {
    title: {
      text: '系统错误率监控'
    },
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: ['错误率']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: generateTimeSeriesData(12, 0, 0).map(item => item[0])
    },
    yAxis: {
      type: 'value',
      name: '错误率(%)',
      max: 5
    },
    series: [
      {
        name: '错误率',
        type: 'line',
        data: generateTimeSeriesData(12, 1.2, 1.5).map(item => item[1]),
        markLine: {
          data: [
            {
              name: '警告阈值',
              yAxis: 2,
              lineStyle: {
                color: '#FF9800'
              }
            },
            {
              name: '严重阈值',
              yAxis: 4,
              lineStyle: {
                color: '#F44336'
              }
            }
          ]
        }
      }
    ]
  }

  return {
    responseTimeChartOptions,
    systemLoadChartOptions,
    requestCountChartOptions,
    errorRateChartOptions
  }
}

// 生成系统可用性数据
export const generateSystemAvailability = () => {
  return {
    current: `${(99.9 + Math.random() * 0.09).toFixed(2)}%`,
    last24h: `${(99.9 + Math.random() * 0.09).toFixed(2)}%`,
    last7d: `${(99.8 + Math.random() * 0.19).toFixed(2)}%`,
    last30d: `${(99.7 + Math.random() * 0.29).toFixed(2)}%`
  }
}

// 定义指标变化类型
type ChangeType = 'increase' | 'decrease';

// 生成服务指标数据
export const generateServiceMetrics = () => {
  return {
    apiRequests: Math.floor(1200000 + Math.random() * 100000).toLocaleString(),
    avgResponseTime: `${Math.floor(120 + Math.random() * 20)}ms`,
    errorRate: `${(0.4 + Math.random() * 0.1).toFixed(2)}%`,
    apiRequestsChange: { 
      value: +(Math.random() * 15).toFixed(1), 
      type: Math.random() > 0.5 ? 'increase' as ChangeType : 'decrease' as ChangeType,
      isGood: Math.random() > 0.5
    },
    avgResponseTimeChange: { 
      value: +(Math.random() * 10).toFixed(1), 
      type: Math.random() > 0.5 ? 'increase' as ChangeType : 'decrease' as ChangeType,
      isGood: Math.random() > 0.5 ? false : true
    },
    errorRateChange: { 
      value: +(Math.random() * 0.3).toFixed(2), 
      type: Math.random() > 0.5 ? 'increase' as ChangeType : 'decrease' as ChangeType,
      isGood: Math.random() > 0.5 ? false : true
    }
  }
}

// 生成告警统计数据
export const generateAlertStats = (alerts: Alert[]) => {
  return {
    active: alerts.filter(alert => alert.status === 'active').length,
    critical: alerts.filter(alert => alert.severity === 'critical' && alert.status === 'active').length,
    resolved: alerts.filter(alert => alert.status === 'resolved').length
  }
}
