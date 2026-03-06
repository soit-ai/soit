import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { useTranslation } from '@/i18n'

interface UsageItem {
  name: string
  value: number
  color: string
}

interface UsageDistributionProps {
  usageItems: UsageItem[]
}

export function UsageDistribution({ usageItems }: UsageDistributionProps) {
  const { t } = useTranslation()
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('bot.monitor.usageDistribution.title')}</CardTitle>
        <CardDescription>{t('bot.monitor.usageDistribution.description')}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[300px] flex items-center justify-center">
          <div className="w-full space-y-6">
            {usageItems.map((item, index) => (
              <div key={index} className="flex items-center gap-4">
                <div className={`h-4 w-4 rounded-full ${item.color}`}></div>
                <div className="flex-1 space-y-1">
                  <div className="flex justify-between">
                    <p className="text-sm font-medium">{item.name}</p>
                    <p className="text-sm font-medium">{item.value}%</p>
                  </div>
                  <Progress value={item.value} className="h-2" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
      <CardFooter className="border-t px-6 py-4">
        <Button variant="outline" size="sm">
          {t('bot.monitor.usageDistribution.viewDetails')}
        </Button>
      </CardFooter>
    </Card>
  )
}
