import React from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export interface HeartbeatData {
  service: string
  timestamps: string[]
  status: ('success' | 'failure' | 'warning')[]
}

interface HeartbeatChartProps {
  title: string
  data: HeartbeatData[]
  timeRange?: number // 显示的时间范围（小时）
  description?: string
}

export function HeartbeatChart({ 
  title, 
  data, 
  timeRange = 24, 
  description 
}: HeartbeatChartProps) {
  // 获取状态对应的颜色
  const getStatusColor = (status: 'success' | 'failure' | 'warning') => {
    switch (status) {
      case 'success':
        return 'bg-green-500'
      case 'warning':
        return 'bg-yellow-500'
      case 'failure':
        return 'bg-red-500'
      default:
        return 'bg-gray-300'
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {data.map((item, index) => (
            <div key={index} className="space-y-1">
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium">{item.service}</span>
                <span className="text-xs text-muted-foreground">过去 {timeRange} 小时</span>
              </div>
              <div className="flex space-x-1 h-8">
                {item.status.map((status, idx) => (
                  <div 
                    key={idx} 
                    className={`flex-1 ${getStatusColor(status)} rounded-sm`}
                    title={`${item.timestamps[idx]}: ${status === 'success' ? '正常' : status === 'warning' ? '警告' : '失败'}`}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
