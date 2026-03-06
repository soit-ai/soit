import { Activity, RefreshCw, Cpu, Users } from 'lucide-react'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { useTranslation } from '@/i18n'

interface Anomaly {
  title: string
  severity: 'critical' | 'warning' | 'info' | 'success'
  description: string
  timestamp: string
  icon: 'activity' | 'cpu' | 'users' | 'refresh'
}

interface AnomalyMonitorProps {
  anomalies: Anomaly[]
  summary?: {
    total: number
    critical: number
  }
}

export function AnomalyMonitor({ anomalies, summary = { total: 0, critical: 0 } }: AnomalyMonitorProps) {
  const { t } = useTranslation()
  const getIconComponent = (icon: string) => {
    switch (icon) {
      case 'activity': return <Activity className="h-4 w-4 text-red-500" />
      case 'cpu': return <Cpu className="h-4 w-4 text-yellow-500" />
      case 'users': return <Users className="h-4 w-4 text-blue-500" />
      case 'refresh': return <RefreshCw className="h-4 w-4 text-green-500" />
      default: return <Activity className="h-4 w-4" />
    }
  }

  const getSeverityStyles = (severity: string) => {
    switch (severity) {
      case 'critical':
        return {
          bg: 'bg-red-50 dark:bg-red-950/20',
          iconBg: 'bg-red-100 dark:bg-red-900/50',
          badgeBg: 'bg-red-100 dark:bg-red-900/50',
          textColor: 'text-red-500'
        }
      case 'warning':
        return {
          bg: 'bg-yellow-50 dark:bg-yellow-950/20',
          iconBg: 'bg-yellow-100 dark:bg-yellow-900/50',
          badgeBg: 'bg-yellow-100 dark:bg-yellow-900/50',
          textColor: 'text-yellow-500'
        }
      case 'info':
        return {
          bg: 'bg-blue-50 dark:bg-blue-950/20',
          iconBg: 'bg-blue-100 dark:bg-blue-900/50',
          badgeBg: 'bg-blue-100 dark:bg-blue-900/50',
          textColor: 'text-blue-500'
        }
      case 'success':
        return {
          bg: 'bg-green-50 dark:bg-green-950/20',
          iconBg: 'bg-green-100 dark:bg-green-900/50',
          badgeBg: 'bg-green-100 dark:bg-green-900/50',
          textColor: 'text-green-500'
        }
      default:
        return {
          bg: 'bg-gray-50 dark:bg-gray-900/20',
          iconBg: 'bg-gray-100 dark:bg-gray-800/50',
          badgeBg: 'bg-gray-100 dark:bg-gray-800/50',
          textColor: 'text-gray-500'
        }
    }
  }

  const getSeverityLabel = (severity: string) => {
    switch (severity) {
      case 'critical': return t('bot.monitor.anomalies.severity.critical')
      case 'warning': return t('bot.monitor.anomalies.severity.warning')
      case 'info': return t('bot.monitor.anomalies.severity.info')
      case 'success': return t('bot.monitor.anomalies.severity.success')
      default: return t('bot.monitor.anomalies.severity.unknown')
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('bot.monitor.anomalies.title')}</CardTitle>
        <CardDescription>{t('bot.monitor.anomalies.description')}</CardDescription>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[300px] w-full rounded-md border">
          <div className="p-4 space-y-4">
            {anomalies.map((anomaly, index) => {
              const styles = getSeverityStyles(anomaly.severity)
              return (
                <div key={index} className={`flex items-start gap-4 p-3 rounded-lg ${styles.bg}`}>
                  <div className={`h-8 w-8 rounded-full ${styles.iconBg} flex items-center justify-center`}>
                    {getIconComponent(anomaly.icon)}
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <p className="font-medium">{anomaly.title}</p>
                      <span className={`px-2 py-0.5 rounded-full text-xs ${styles.badgeBg} ${styles.textColor}`}>
                        {getSeverityLabel(anomaly.severity)}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground">{anomaly.description}</p>
                    <p className="text-xs text-muted-foreground">{anomaly.timestamp}</p>
                  </div>
                </div>
              )
            })}
          </div>
        </ScrollArea>
      </CardContent>
      <CardFooter className="border-t px-6 py-4">
        <div className="flex justify-between items-center w-full">
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {t('bot.monitor.anomalies.summary', { total: summary.total, critical: summary.critical })}
            </span>
          </div>
          <Button variant="outline" size="sm">
            {t('bot.monitor.anomalies.viewAll')}
          </Button>
        </div>
      </CardFooter>
    </Card>
  )
}
