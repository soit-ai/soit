import { Download, Users } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useTranslation } from '@/i18n'

interface UserGroup {
  name: string
  iconColor: string
  userCount: number
  sessionCount: number
  avgSessionDuration: string
  tokenUsage: string
  satisfaction: number
}

interface UserStatsTableProps {
  userGroups: UserGroup[]
  summary: {
    totalUsers: number
    totalSessions: number
  }
}

export function UserStatsTable({ userGroups, summary }: UserStatsTableProps) {
  const { t } = useTranslation()
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('bot.monitor.userStats.title')}</CardTitle>
        <CardDescription>{t('bot.monitor.userStats.description')}</CardDescription>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[400px] w-full rounded-md">
          <table className="w-full">
            <thead>
              <tr className="border-b">
                <th className="text-left p-2 font-medium">{t('bot.monitor.userStats.columns.group')}</th>
                <th className="text-left p-2 font-medium">{t('bot.monitor.userStats.columns.users')}</th>
                <th className="text-left p-2 font-medium">{t('bot.monitor.userStats.columns.sessions')}</th>
                <th className="text-left p-2 font-medium">{t('bot.monitor.userStats.columns.avgDuration')}</th>
                <th className="text-left p-2 font-medium">{t('bot.monitor.userStats.columns.tokens')}</th>
                <th className="text-left p-2 font-medium">{t('bot.monitor.userStats.columns.satisfaction')}</th>
              </tr>
            </thead>
            <tbody>
              {userGroups.map((group, index) => (
                <tr key={index} className={index < userGroups.length - 1 ? "border-b hover:bg-muted/50" : "hover:bg-muted/50"}>
                  <td className="p-2">
                    <div className="flex items-center gap-2">
                      <Users className={`h-4 w-4 ${group.iconColor}`} />
                      <span>{group.name}</span>
                    </div>
                  </td>
                  <td className="p-2">{group.userCount}</td>
                  <td className="p-2">{group.sessionCount}</td>
                  <td className="p-2">{group.avgSessionDuration}</td>
                  <td className="p-2">{group.tokenUsage}</td>
                  <td className="p-2">
                    <div className="flex items-center gap-2">
                      <span>{group.satisfaction}%</span>
                      <div className="h-2 w-16 bg-muted rounded-full overflow-hidden">
                        <div 
                          className={`h-full ${group.satisfaction >= 90 ? 'bg-green-500' : 'bg-yellow-500'} rounded-full`} 
                          style={{ width: `${group.satisfaction}%` }}
                        ></div>
                      </div>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollArea>
      </CardContent>
      <CardFooter className="border-t px-6 py-4">
        <div className="flex justify-between items-center w-full">
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {t('bot.monitor.userStats.summary', { users: summary.totalUsers, sessions: summary.totalSessions })}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm">
              <Download className="h-4 w-4 mr-1" />
              {t('bot.monitor.userStats.exportReport')}
            </Button>
            <Button variant="outline" size="sm">
              {t('bot.monitor.userStats.viewAll')}
            </Button>
          </div>
        </div>
      </CardFooter>
    </Card>
  )
}
