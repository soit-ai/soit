import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { format } from 'date-fns'
import { enUS, zhCN } from 'date-fns/locale'
import { useTranslation } from '@/i18n'

interface ModelStatsProps {
  providerId: string
  modelId: string
  modelName: string
}

interface UsageStats {
  date: string
  requests: number
  tokens: number
  cost: number
}

export function ModelStats({ providerId, modelId, modelName }: ModelStatsProps) {
  const { t, i18n } = useTranslation()
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState<UsageStats[]>([])
  const [timeRange, setTimeRange] = useState<'day' | 'week' | 'month'>('week')
  const currencySymbol = t('system.model.stats.currency')
  const dateLocale = i18n.language === 'zh-CN' ? zhCN : enUS

  useEffect(() => {
    loadStats()
  }, [providerId, modelId, timeRange])

  const loadStats = async () => {
    setLoading(true)
    try {
      setStats([])
    } catch (error) {
      console.error('Failed to load stats:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatDate = (date: string) => {
    return format(new Date(date), 'MM-dd', { locale: dateLocale })
  }

  const formatValue = (value: number) => {
    return value.toLocaleString(i18n.language)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('system.model.stats.title')}</CardTitle>
        <CardDescription>
          {t('system.model.stats.description', { modelName })}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="week" onValueChange={(value) => setTimeRange(value as 'day' | 'week' | 'month')}>
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="day">{t('system.model.stats.range.day')}</TabsTrigger>
            <TabsTrigger value="week">{t('system.model.stats.range.week')}</TabsTrigger>
            <TabsTrigger value="month">{t('system.model.stats.range.month')}</TabsTrigger>
          </TabsList>
          <TabsContent value={timeRange} className="mt-4">
            <div className="h-[300px]">
              {loading ? (
                <div className="flex items-center justify-center h-full">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                </div>
              ) : stats.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={stats}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="date"
                      tickFormatter={formatDate}
                      tick={{ fontSize: 12 }}
                    />
                    <YAxis
                      yAxisId="left"
                      tickFormatter={formatValue}
                      tick={{ fontSize: 12 }}
                    />
                    <YAxis
                      yAxisId="right"
                      orientation="right"
                      tickFormatter={(value) => `${currencySymbol}${formatValue(value)}`}
                      tick={{ fontSize: 12 }}
                    />
                    <Tooltip
                      formatter={(value: number, name: string) => {
                        if (name === 'cost') {
                          return [`${currencySymbol}${formatValue(value)}`, t('system.model.stats.tooltip.cost')]
                        }
                        return [formatValue(value), name === 'requests' ? t('system.model.stats.tooltip.requests') : t('system.model.stats.tooltip.tokens')]
                      }}
                      labelFormatter={formatDate}
                    />
                    <Line
                      yAxisId="left"
                      type="monotone"
                      dataKey="requests"
                      stroke="#8884d8"
                      name="requests"
                    />
                    <Line
                      yAxisId="left"
                      type="monotone"
                      dataKey="tokens"
                      stroke="#82ca9d"
                      name="tokens"
                    />
                    <Line
                      yAxisId="right"
                      type="monotone"
                      dataKey="cost"
                      stroke="#ff7300"
                      name="cost"
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
                  {t('system.model.stats.empty')}
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
} 
