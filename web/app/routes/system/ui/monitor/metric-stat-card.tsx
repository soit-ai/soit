import React from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ArrowDown, ArrowUp } from 'lucide-react'

export interface MetricStatProps {
  title: string
  value: string | number
  icon?: React.ReactNode
  description?: string
  change?: {
    value: number
    type: 'increase' | 'decrease'
    isGood?: boolean // 增加是否为好事
  }
}

export function MetricStatCard({
  title,
  value,
  icon,
  description,
  change
}: MetricStatProps) {
  // 确定变化的显示样式
  const getChangeDisplay = () => {
    if (!change) return null

    const isPositive = change.type === 'increase'
    const isGood = change.isGood !== undefined 
      ? change.isGood 
      : (change.type === 'increase')

    const colorClass = isGood ? 'text-green-600' : 'text-red-600'
    const Icon = isPositive ? ArrowUp : ArrowDown
    
    return (
      <div className={`flex items-center ${colorClass}`}>
        <Icon className="h-4 w-4 mr-1" />
        <span className="text-sm">{Math.abs(change.value)}%</span>
      </div>
    )
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="flex items-baseline justify-between">
          <div className="text-2xl font-bold">{value}</div>
          {getChangeDisplay()}
        </div>
        {description && <p className="text-xs text-muted-foreground mt-2">{description}</p>}
      </CardContent>
    </Card>
  )
}
