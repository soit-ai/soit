import React, { useEffect, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { BarChart, LineChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { init, use, type ECharts } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

use([
  BarChart,
  CanvasRenderer,
  GridComponent,
  LegendComponent,
  LineChart,
  MarkLineComponent,
  TitleComponent,
  TooltipComponent,
])

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
  const chartInstance = useRef<ECharts | null>(null)

  useEffect(() => {
    // Initialize the chart only after the container is mounted.
    if (chartRef.current) {
      if (!chartInstance.current) {
        chartInstance.current = init(chartRef.current)
      }

      chartInstance.current.setOption(options)
    }

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
