import type { Service } from './service-status-table'
import type { Alert } from './alert-list'
import type { HeartbeatData } from './heartbeat-chart'

// 获取当前时间
const now = new Date()

// 格式化时间
const formatTime = (minutesAgo: number): string => {
  const date = new Date(now.getTime() - minutesAgo * 60 * 1000)
  return date.toISOString()
}

// 服务状态数据
export const mockServices: Service[] = [
  {
    id: 'srv-001',
    name: 'API服务',
    status: 'healthy',
    uptime: '99.98%',
    responseTime: '120ms',
    lastChecked: formatTime(2)
  },
  {
    id: 'srv-002',
    name: '数据库服务',
    status: 'healthy',
    uptime: '99.95%',
    responseTime: '45ms',
    lastChecked: formatTime(2)
  },
  {
    id: 'srv-003',
    name: '认证服务',
    status: 'warning',
    uptime: '99.5%',
    responseTime: '350ms',
    lastChecked: formatTime(2)
  },
  {
    id: 'srv-004',
    name: '存储服务',
    status: 'healthy',
    uptime: '99.99%',
    responseTime: '85ms',
    lastChecked: formatTime(2)
  },
  {
    id: 'srv-005',
    name: '消息队列',
    status: 'critical',
    uptime: '95.2%',
    responseTime: '520ms',
    lastChecked: formatTime(2)
  }
]

// 系统资源使用数据
export const mockSystemResources = {
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

// 告警数据
export const mockAlerts: Alert[] = [
  {
    id: 'alert-001',
    service: '消息队列',
    severity: 'critical',
    message: '服务响应时间超过阈值',
    timestamp: formatTime(45),
    status: 'active'
  },
  {
    id: 'alert-002',
    service: '认证服务',
    severity: 'warning',
    message: '内存使用率超过80%',
    timestamp: formatTime(30),
    status: 'active'
  },
  {
    id: 'alert-003',
    service: 'API服务',
    severity: 'info',
    message: '服务重启成功',
    timestamp: formatTime(135),
    status: 'resolved'
  },
  {
    id: 'alert-004',
    service: '数据库服务',
    severity: 'warning',
    message: '数据库连接池接近上限',
    timestamp: formatTime(180),
    status: 'resolved'
  },
  {
    id: 'alert-005',
    service: '存储服务',
    severity: 'info',
    message: '存储空间清理完成',
    timestamp: formatTime(240),
    status: 'resolved'
  }
]

// 心跳数据
export const mockHeartbeatData: HeartbeatData[] = [
  {
    service: 'API服务',
    timestamps: Array.from({ length: 24 }, (_, i) => formatTime(i * 60)),
    status: Array.from({ length: 24 }, () => Math.random() > 0.05 ? 'success' : Math.random() > 0.5 ? 'warning' : 'failure')
  },
  {
    service: '数据库服务',
    timestamps: Array.from({ length: 24 }, (_, i) => formatTime(i * 60)),
    status: Array.from({ length: 24 }, () => Math.random() > 0.03 ? 'success' : Math.random() > 0.5 ? 'warning' : 'failure')
  },
  {
    service: '认证服务',
    timestamps: Array.from({ length: 24 }, (_, i) => formatTime(i * 60)),
    status: Array.from({ length: 24 }, () => Math.random() > 0.1 ? 'success' : Math.random() > 0.5 ? 'warning' : 'failure')
  },
  {
    service: '存储服务',
    timestamps: Array.from({ length: 24 }, (_, i) => formatTime(i * 60)),
    status: Array.from({ length: 24 }, () => Math.random() > 0.02 ? 'success' : Math.random() > 0.5 ? 'warning' : 'failure')
  },
  {
    service: '消息队列',
    timestamps: Array.from({ length: 24 }, (_, i) => formatTime(i * 60)),
    status: Array.from({ length: 24 }, () => Math.random() > 0.15 ? 'success' : Math.random() > 0.5 ? 'warning' : 'failure')
  }
]

// 生成时间序列数据
const generateTimeSeriesData = (hours: number, baseValue: number, volatility: number) => {
  return Array.from({ length: hours }, (_, i) => {
    const time = new Date(now.getTime() - (hours - i) * 60 * 60 * 1000)
    const value = baseValue + (Math.random() - 0.5) * volatility
    return [time.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }), Math.max(0, Number(value.toFixed(2)))]
  })
}

// 响应时间图表数据
export const responseTimeChartOptions = {
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
export const systemLoadChartOptions = {
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
export const requestCountChartOptions = {
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
export const errorRateChartOptions = {
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
