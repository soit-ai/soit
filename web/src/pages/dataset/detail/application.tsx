import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Settings, Trash2, ExternalLink, Clock, Activity, CheckCircle2, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import { PageHeader } from './ui/application/page-header'
import { useNavLayout } from '@/components/layout/nav-layout'
import { useTranslation } from '@/i18n'

// Mock data for applications.
const mockApplications = [
  {
    id: '1',
    nameKey: 'dataset.application.mock.supportAssistant.name',
    descriptionKey: 'dataset.application.mock.supportAssistant.description',
    type: 'chatbot',
    status: 'active',
    createdAt: '2024-03-01',
    lastUsed: '2024-03-20',
    apiKey: 'sk-xxxxx',
    usage: {
      totalQueries: 1500,
      successRate: 98.5,
      averageResponseTime: 1.2,
    },
  },
  {
    id: '2',
    nameKey: 'dataset.application.mock.searchSystem.name',
    descriptionKey: 'dataset.application.mock.searchSystem.description',
    type: 'search',
    status: 'inactive',
    createdAt: '2024-03-05',
    lastUsed: '2024-03-15',
    apiKey: 'sk-yyyyy',
    usage: {
      totalQueries: 800,
      successRate: 99.0,
      averageResponseTime: 0.8,
    },
  },
]

function Page() {
  const { t } = useTranslation()
  const [searchQuery, setSearchQuery] = useState('')
  const { setHeaderContent } = useNavLayout()

  useEffect(() => {
    setHeaderContent(<PageHeader title={t('dataset.application.header.title')} onRefresh={handleRefresh} />)
    return () => setHeaderContent(null)
  }, [setHeaderContent, t])

  const handleRefresh = () => {
  }

  const filteredApplications = mockApplications.filter((app) => {
    const name = t(app.nameKey)
    const description = t(app.descriptionKey)
    return name.toLowerCase().includes(searchQuery.toLowerCase()) || description.toLowerCase().includes(searchQuery.toLowerCase())
  })

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">

      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 3xl:grid-cols-5">
        {filteredApplications.map((app) => (
          <Card key={app.id} className="w-full hover:shadow-lg transition-shadow duration-200">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg font-semibold">{t(app.nameKey)}</CardTitle>
                <Badge variant={app.status === 'active' ? 'default' : 'secondary'} className={cn('px-2 py-1', app.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700')}>
                  {app.status === 'active' ? <CheckCircle2 className="mr-1 h-3 w-3" /> : <XCircle className="mr-1 h-3 w-3" />}
                  {app.status === 'active'
                    ? t('dataset.application.status.active')
                    : t('dataset.application.status.inactive')}
                </Badge>
              </div>
              <div className="h-[40px] mt-1.5">
                <CardDescription className="line-clamp-2">{t(app.descriptionKey)}</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 text-sm">
                <div className="flex items-center text-muted-foreground">
                  <Clock className="mr-2 h-4 w-4" />
                  <span>{t('dataset.application.fields.createdAt', { date: app.createdAt })}</span>
                </div>
                <div className="flex items-center text-muted-foreground">
                  <Activity className="mr-2 h-4 w-4" />
                  <span>{t('dataset.application.fields.lastUsed', { date: app.lastUsed })}</span>
                </div>
                <div className="flex items-center justify-between pt-2 border-t">
                  <span className="text-muted-foreground">{t('dataset.application.fields.totalQueries')}</span>
                  <span className="font-medium">{app.usage.totalQueries}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">{t('dataset.application.fields.successRate')}</span>
                  <span className="font-medium text-green-600">{app.usage.successRate}%</span>
                </div>
              </div>
              <div className="flex gap-2 mt-4 pt-4 border-t">
                <Button variant="outline" size="sm" className="flex-1 h-9">
                  <Settings className="mr-2 h-4 w-4" />
                  {t('dataset.application.actions.settings')}
                </Button>
                <Button variant="outline" size="sm" className="flex-1 h-9">
                  <ExternalLink className="mr-2 h-4 w-4" />
                  {t('dataset.application.actions.open')}
                </Button>
                <Button variant="outline" size="sm" className="flex-1 h-9 text-destructive hover:text-destructive">
                  <Trash2 className="mr-2 h-4 w-4" />
                  {t('dataset.application.actions.delete')}
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

export default Page
