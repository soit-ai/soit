import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router'
import { Activity, AppWindow, ArrowRight, Clock, Database } from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useNavLayout } from '@/components/layout/nav-layout'
import { PageHeader } from './ui/usages/page-header'
import { useTranslation } from '@/i18n'
import { useNavigate } from '@/hooks/use-navigate'
import { listKnowledgeUsages, type KnowledgeUsage } from '@/services/knowledge-service'
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
  const [usages, setUsages] = useState<KnowledgeUsage[]>([])
  const [loading, setLoading] = useState(false)

  const fetchUsages = useCallback(async () => {
    if (!knowledgeId) return
    try {
      setLoading(true)
      setUsages(await listKnowledgeUsages(knowledgeId))
    } catch (error) {
      console.error('Failed to fetch knowledge usages:', error)
    } finally {
      setLoading(false)
    }
  }, [knowledgeId])

  useEffect(() => {
    setHeaderContent(<PageHeader title={t('knowledge.usages.header.title')} onRefresh={fetchUsages} />)
    return () => setHeaderContent(null)
  }, [setHeaderContent, t, fetchUsages])

  useEffect(() => {
    fetchUsages()
  }, [fetchUsages])

  const openResource = (item: KnowledgeUsage) => {
    if (item.resource_kind?.toLowerCase() === 'workflow') {
      navigate(`/workflow/${item.resource_id}/build`)
      return
    }
    navigate(`/agents/${item.resource_id}`)
  }

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      {loading && <div className="text-sm text-muted-foreground">{t('knowledge.usages.actions.refresh')}</div>}
      {!loading && usages.length === 0 && (
        <Card>
          <CardHeader>
            <CardTitle>{t('knowledge.usages.header.title')}</CardTitle>
            <CardDescription>No agents or workflows are currently bound to this knowledge base.</CardDescription>
          </CardHeader>
        </Card>
      )}

      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 xl:grid-cols-3">
        {usages.map((usage) => (
          <Card key={usage.resource_version_id} className="hover:border-primary/40 transition-colors">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <AppWindow className="h-4 w-4" />
                    {usage.resource_name}
                  </CardTitle>
                  <CardDescription>{usage.resource_kind} · v{usage.resource_version}</CardDescription>
                </div>
                <Badge variant="outline">{usage.resource_status}</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid gap-2 text-sm text-muted-foreground">
                <div className="flex items-center gap-2">
                  <Database className="h-4 w-4" />
                  Version status: {usage.resource_version_status}
                </div>
                <div className="flex items-center gap-2">
                  <Activity className="h-4 w-4" />
                  Run count: {usage.run_count}
                </div>
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  Last run: {formatTimestamp(usage.last_run_at)}
                </div>
              </div>
              <Button variant="outline" className="w-full" onClick={() => openResource(usage)}>
                Open Resource
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
