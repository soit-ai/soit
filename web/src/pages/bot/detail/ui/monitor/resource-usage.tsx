import { Zap } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { useTranslation } from '@/i18n'

interface ResourceItem {
  name: string
  description: string
  value: number
}

interface ResourceUsageProps {
  resources: ResourceItem[]
}

export function ResourceUsage({ resources }: ResourceUsageProps) {
  const { t } = useTranslation()
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('bot.monitor.resources.title')}</CardTitle>
        <CardDescription>{t('bot.monitor.resources.description')}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-8">
          {resources.map((resource, index) => (
            <div key={index}>
              <div className="flex items-center justify-between mb-2">
                <div className="space-y-1">
                  <p className="text-sm font-medium">{resource.name}</p>
                  <p className="text-sm text-muted-foreground">{resource.description}</p>
                </div>
                <p className="text-xl font-bold">{resource.value}%</p>
              </div>
              <Progress value={resource.value} className="h-2" />
            </div>
          ))}
        </div>
      </CardContent>
      <CardFooter className="border-t px-6 py-4">
        <div className="flex justify-between items-center w-full text-sm">
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-green-500" />
            <span className="text-green-500">{t('bot.monitor.resources.statusGood')}</span>
          </div>
          <Button variant="outline" size="sm">
            {t('bot.monitor.resources.viewReport')}
          </Button>
        </div>
      </CardFooter>
    </Card>
  )
}
