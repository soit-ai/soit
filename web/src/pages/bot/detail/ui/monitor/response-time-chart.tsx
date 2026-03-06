import { Activity, Clock } from 'lucide-react'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { useTranslation } from '@/i18n'

interface ResponseTimeChartProps {
  responseTimeData: number[]
  avgResponseTime: number
  targetTime?: number
}

export function ResponseTimeChart({ responseTimeData, avgResponseTime, targetTime = 2 }: ResponseTimeChartProps) {
  const { t } = useTranslation()
  const maxValue = Math.max(...responseTimeData)
  const formatSeconds = (value: number) => t('bot.monitor.units.seconds', { value: value.toFixed(1) })
  
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('bot.monitor.responseTime.title')}</CardTitle>
        <CardDescription>{t('bot.monitor.responseTime.description')}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[300px] flex items-center justify-center">
          <div className="w-full">
            <div className="flex items-center justify-between mb-8">
              <div className="space-y-1">
                <p className="text-sm font-medium">{t('bot.monitor.responseTime.currentAvg')}</p>
                <p className="text-3xl font-bold">{formatSeconds(avgResponseTime)}</p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">{t('bot.monitor.responseTime.targetLabel', { value: targetTime })}</span>
                <div className={`h-3 w-3 rounded-full ${avgResponseTime < targetTime ? 'bg-green-500' : 'bg-yellow-500'}`}></div>
              </div>
            </div>
            
            <div className="space-y-4">
              <div className="relative h-[200px] w-full">
                <div className="absolute inset-0 flex items-end justify-between px-2">
                  {responseTimeData.map((time, index) => (
                    <div key={index} className="flex flex-col items-center">
                      <div 
                        className="bg-primary w-12 rounded-t-md" 
                        style={{ height: `${(time / maxValue) * 150}px` }}
                      ></div>
                      <span className="text-xs mt-2">{t('bot.monitor.responseTime.dayLabel', { value: 6 - index })}</span>
                      <span className="text-xs text-muted-foreground">{formatSeconds(time)}</span>
                    </div>
                  ))}
                </div>
                
                <div 
                  className="absolute border-t border-dashed border-yellow-500 w-full" 
                  style={{ bottom: `${(targetTime / maxValue) * 150 + 24}px` }}
                >
                  <span className="absolute -top-6 right-0 text-xs text-yellow-500">
                    {t('bot.monitor.responseTime.targetLine', { value: targetTime })}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
      <CardFooter className="border-t px-6 py-4">
        <div className="flex justify-between items-center w-full text-sm">
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground">
              {t('bot.monitor.responseTime.fastest', { value: '0.8' })}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground">
              {t('bot.monitor.responseTime.slowest', { value: '3.2' })}
            </span>
          </div>
        </div>
      </CardFooter>
    </Card>
  )
}
