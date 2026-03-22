import React, { useEffect, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import * as echarts from 'echarts'

export interface ChartOptions {
  title?: string | {
    text: string
    [key: string]: any
  }
  tooltip?: any
  legend?: any
  xAxis?: any
  yAxis?: any
  series?: any[]
  grid?: any
  color?: string[]
  toolbox?: any
  dataZoom?: any[]
  [key: string]: any
}

interface MonitorChartProps {
  title: string
  options: ChartOptions
  height?: number
  description?: string
  className?: string
}

export function MonitorChart({ title, options, height = 300, description, className }: MonitorChartProps) {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    // 初始化图表
    if (chartRef.current) {
      if (!chartInstance.current) {
        chartInstance.current = echarts.init(chartRef.current)
      }
      
      // 设置图表选项
      chartInstance.current.setOption(options)
    }

    // 处理窗口大小变化
    const handleResize = () => {
      chartInstance.current?.resize()
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chartInstance.current?.dispose()
      chartInstance.current = null
    }
  }, [options])

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </CardHeader>
      <CardContent>
        <div ref={chartRef} style={{ height: `${height}px`, width: '100%' }} />
      </CardContent>
    </Card>
  )
}
