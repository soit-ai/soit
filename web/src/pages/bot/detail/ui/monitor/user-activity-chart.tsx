import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { useTranslation } from '@/i18n'

interface UserActivityChartProps {
  dailyActiveUsers: number[]
  days?: string[]
}

export function UserActivityChart({ dailyActiveUsers, days }: UserActivityChartProps) {
  const { t } = useTranslation()
  const labelDays = days ?? [
    t('bot.monitor.userActivity.days.mon'),
    t('bot.monitor.userActivity.days.tue'),
    t('bot.monitor.userActivity.days.wed'),
    t('bot.monitor.userActivity.days.thu'),
    t('bot.monitor.userActivity.days.fri'),
    t('bot.monitor.userActivity.days.sat'),
    t('bot.monitor.userActivity.days.sun'),
  ]
  const maxValue = Math.max(...dailyActiveUsers)
  
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('bot.monitor.userActivity.title')}</CardTitle>
        <CardDescription>{t('bot.monitor.userActivity.description')}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[300px] flex items-center justify-center">
          <div className="w-full h-full flex flex-col justify-center">
            {dailyActiveUsers.map((value, index) => (
              <div key={index}>
                <div className="flex justify-between mb-2">
                  <span className="text-sm text-muted-foreground">{labelDays[index]}</span>
                  <span className="text-sm font-medium">{value}</span>
                </div>
                <Progress 
                  value={value / maxValue * 100} 
                  className={`h-2 ${index < dailyActiveUsers.length - 1 ? 'mb-4' : ''}`} 
                />
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
