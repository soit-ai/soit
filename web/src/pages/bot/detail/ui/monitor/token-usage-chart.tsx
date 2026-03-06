import { TrendingUp, Zap } from 'lucide-react'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { useTranslation } from '@/i18n'

interface TokenUsageChartProps {
  usageByDay: number[]
  totalTokens: number
}

export function TokenUsageChart({ usageByDay, totalTokens }: TokenUsageChartProps) {
  const { t } = useTranslation()
  const maxValue = Math.max(...usageByDay)
  const averageDaily = totalTokens / usageByDay.length
  
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('bot.monitor.tokenUsage.title')}</CardTitle>
        <CardDescription>{t('bot.monitor.tokenUsage.description')}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[300px] flex items-center justify-center">
          <div className="w-full">
            <div className="flex items-center justify-between mb-8">
              <div className="space-y-1">
                <p className="text-sm font-medium">{t('bot.monitor.tokenUsage.total')}</p>
                <p className="text-3xl font-bold">
                  {t('bot.monitor.units.tokensK', { value: (totalTokens / 1000).toFixed(1) })}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">
                  {t('bot.monitor.tokenUsage.averageDaily', { value: (averageDaily / 1000).toFixed(1) })}
                </span>
              </div>
            </div>
            
            <div className="space-y-4">
              <div className="relative h-[200px] w-full">
                <div className="absolute inset-0 flex items-end justify-between px-2">
                  {usageByDay.map((usage, index) => (
                    <div key={index} className="flex flex-col items-center">
                      <div 
                        className="bg-primary/80 w-12 rounded-t-md" 
                        style={{ height: `${(usage / maxValue) * 150}px` }}
                      ></div>
                      <span className="text-xs mt-2">{t('bot.monitor.tokenUsage.dayLabel', { value: 6 - index })}</span>
                      <span className="text-xs text-muted-foreground">
                        {t('bot.monitor.units.tokensK', { value: (usage / 1000).toFixed(1) })}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
      <CardFooter className="border-t px-6 py-4">
        <div className="flex justify-between items-center w-full text-sm">
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground">
              {t('bot.monitor.tokenUsage.peak', { value: (maxValue / 1000).toFixed(1) })}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-green-500" />
            <span className="text-green-500">{t('bot.monitor.tokenUsage.growth', { value: '+15.2%' })}</span>
          </div>
        </div>
      </CardFooter>
    </Card>
  )
}
