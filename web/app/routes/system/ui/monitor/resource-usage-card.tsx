import React from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'

export interface ResourceUsageProps {
  title: string
  usagePercentage: number
  icon?: React.ReactNode
  details?: string | { label: string; value: string }[]
  progressColor?: string
}

export function ResourceUsageCard({
  title,
  usagePercentage,
  icon,
  details,
  progressColor = 'bg-primary'
}: ResourceUsageProps) {
  // 根据使用率确定颜色
  const getProgressColorClass = () => {
    if (progressColor) return progressColor
    
    if (usagePercentage >= 90) return 'bg-destructive'
    if (usagePercentage >= 70) return 'bg-warning'
    return 'bg-primary'
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{usagePercentage}%</div>
        <div className="mt-2 h-2 w-full rounded-full bg-primary/10 overflow-hidden">
          <div 
            className={`h-full rounded-full ${getProgressColorClass()}`} 
            style={{ width: `${usagePercentage}%` }}
          />
        </div>
        {details && typeof details === 'string' ? (
          <p className="text-xs text-muted-foreground mt-2">{details}</p>
        ) : details && Array.isArray(details) ? (
          <div className="flex justify-between text-xs text-muted-foreground mt-2">
            {details.map((item, index) => (
              <div key={index}>
                <span>{item.label}: </span>
                <span className="font-medium">{item.value}</span>
              </div>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
