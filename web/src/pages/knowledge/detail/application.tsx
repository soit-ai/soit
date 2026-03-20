import { useEffect, useState } from 'react'
import { useParams } from 'react-router'
import { Activity, AppWindow, ArrowRight, Clock, Database } from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useNavLayout } from '@/components/layout/nav-layout'
import { PageHeader } from './ui/application/page-header'
import { useTranslation } from '@/i18n'
import type { TranslationKey } from '@/i18n/types'
import { useNavigate } from '@/hooks/use-navigate'
import { listKnowledgeApplications, type KnowledgeBindingUsage } from '@/services/knowledge-service'
import { formatDateTime, isoToZonedDate } from '@/utils/date-time'

const formatTimestamp = (value?: string | null) => {
  if (!value) return '-'
  return formatDateTime(isoToZonedDate(value))
}

function Page() {
  const { t } = useTranslation()
  const { knowledgeId } = useParams<{ knowledgeId: string }>()
  const navigate = useNavigate()
  const { setHeaderContent } = useNavLayout()
  const [applications, setApplications] = useState<KnowledgeBindingUsage[]>([])
  const [loading, setLoading] = useState(false)

  const fetchApplications = async () => {
    if (!knowledgeId) return
    try {
      setLoading(true)
      setApplications(await listKnowledgeApplications(knowledgeId))
    } catch (error) {
      console.error('Failed to fetch knowledge applications:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setHeaderContent(<PageHeader title={t('knowledge.application.header.title')} onRefresh={fetchApplications} />)
    return () => setHeaderContent(null)
  }, [setHeaderContent, t, knowledgeId])

  useEffect(() => {
    fetchApplications()
  }, [knowledgeId])

  const openApplication = (item: KnowledgeBindingUsage) => {
    if (item.resource_kind?.toLowerCase() === 'workflow') {
      navigate(`/workflow/${item.resource_id}/build`)
      return
    }
    navigate(`/agents/${item.resource_id}`)
  }

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      {loading && <div className="text-sm text-muted-foreground">{t('knowledge.application.header.refresh' as TranslationKey)}</div>}
      {!loading && applications.length === 0 && (
        <Card>
          <CardHeader>
            <CardTitle>{t('knowledge.application.header.title')}</CardTitle>
            <CardDescription>No agents or workflows are currently bound to this knowledge base.</CardDescription>
          </CardHeader>
        </Card>
      )}

      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 xl:grid-cols-3">
        {applications.map((app) => (
          <Card key={app.resource_version_id} className="hover:border-primary/40 transition-colors">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <AppWindow className="h-4 w-4" />
                    {app.resource_name}
                  </CardTitle>
                  <CardDescription>{app.resource_kind} · v{app.resource_version}</CardDescription>
                </div>
                <Badge variant="outline">{app.resource_status}</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid gap-2 text-sm text-muted-foreground">
                <div className="flex items-center gap-2">
                  <Database className="h-4 w-4" />
                  Version status: {app.resource_version_status}
                </div>
                <div className="flex items-center gap-2">
                  <Activity className="h-4 w-4" />
                  Run count: {app.run_count}
                </div>
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  Last run: {formatTimestamp(app.last_run_at)}
                </div>
              </div>
              <Button variant="outline" className="w-full" onClick={() => openApplication(app)}>
                Open Application
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

export default Page
