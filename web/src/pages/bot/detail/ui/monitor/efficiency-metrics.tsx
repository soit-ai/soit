import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { useTranslation } from '@/i18n'

interface MetricItem {
  name: string
  description: string
  value: string | number
}

interface EfficiencyMetricsProps {
  metrics: MetricItem[]
}

export function EfficiencyMetrics({ metrics }: EfficiencyMetricsProps) {
  const { t } = useTranslation()
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('bot.monitor.efficiency.title')}</CardTitle>
        <CardDescription>{t('bot.monitor.efficiency.description')}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-8">
          {metrics.map((metric, index) => (
            <div key={index}>
              <div className="flex items-center justify-between mb-2">
                <div className="space-y-1">
                  <p className="text-sm font-medium">{metric.name}</p>
                  <p className="text-sm text-muted-foreground">{metric.description}</p>
                </div>
                <p className="text-xl font-bold">{metric.value}</p>
              </div>
              <Progress value={parseFloat(metric.value as string)} className="h-2" />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
