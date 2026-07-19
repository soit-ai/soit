import { useCallback, useEffect, useState } from 'react'
import {
  Activity,
  Clock3,
  Database,
  HardDrive,
  MemoryStick,
  RefreshCw,
  ServerCog,
  ShieldAlert,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useTranslation } from '@/i18n'
import {
  getDiagnosticsSnapshot,
  type DependencyDiagnostic,
  type DiagnosticsSnapshot,
} from '@/services/diagnostics-service'
import { useUserStore } from '@/stores/user'

const formatBytes = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${Math.round(bytes / 1024)} KB`
  if (bytes < 1024 ** 3) return `${Math.round(bytes / 1024 ** 2)} MB`
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`
}

const formatDuration = (seconds: number) => {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
  const hours = Math.floor(seconds / 3600)
  return `${hours}h ${Math.floor((seconds % 3600) / 60)}m`
}

function DependencyCard({ diagnostic }: { diagnostic: DependencyDiagnostic }) {
  const { t } = useTranslation()
  const Icon = diagnostic.name === 'database' ? Database : HardDrive
  const healthy = diagnostic.status === 'healthy'
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <Icon className="size-4 text-primary" />
            <CardTitle className="text-base">{t(`system.diagnostics.dependencies.${diagnostic.name}`)}</CardTitle>
          </div>
          <Badge variant={healthy ? 'success' : 'destructive'}>
            {t(`system.diagnostics.status.${diagnostic.status}`)}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-1 text-sm">
        <p className="text-muted-foreground">
          {t('system.diagnostics.dependencies.latency', { value: diagnostic.latency_ms.toFixed(2) })}
        </p>
        {diagnostic.message && <p className="font-mono text-xs text-destructive">{diagnostic.message}</p>}
      </CardContent>
    </Card>
  )
}

export default function DiagnosticsPage() {
  const { t, i18n } = useTranslation()
  const currentUser = useUserStore((state) => state.currentUser)
  const isOwner = currentUser?.workspace_role?.toLowerCase() === 'owner'
  const [snapshot, setSnapshot] = useState<DiagnosticsSnapshot | null>(null)
  const [loading, setLoading] = useState(false)
  const [failed, setFailed] = useState(false)

  const loadSnapshot = useCallback(async () => {
    try {
      setLoading(true)
      setFailed(false)
      setSnapshot(await getDiagnosticsSnapshot())
    } catch (error) {
      console.error('Failed to load diagnostics snapshot:', error)
      setFailed(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!isOwner) return
    void loadSnapshot()
    const interval = window.setInterval(() => void loadSnapshot(), 30_000)
    return () => window.clearInterval(interval)
  }, [isOwner, loadSnapshot])

  if (!currentUser) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-sm text-muted-foreground">
        {t('system.diagnostics.loadingUser')}
      </div>
    )
  }

  if (!isOwner) {
    return (
      <div className="mx-auto flex min-h-[50vh] max-w-xl flex-col items-center justify-center gap-3 p-6 text-center">
        <ShieldAlert className="size-10 text-muted-foreground" />
        <h1 className="text-xl font-bold">{t('system.diagnostics.access.title')}</h1>
        <p className="text-sm text-muted-foreground">{t('system.diagnostics.access.description')}</p>
      </div>
    )
  }

  const workspaceMetrics = snapshot
    ? [
        ['agents', snapshot.workspace.agents],
        ['workflows', snapshot.workspace.workflows],
        ['knowledgeBases', snapshot.workspace.knowledge_bases],
        ['plugins', snapshot.workspace.plugins],
        ['models', snapshot.workspace.models],
        ['threads', snapshot.workspace.threads],
        ['activeRuns', snapshot.workspace.active_runs],
        ['failedRuns24h', snapshot.workspace.failed_runs_24h],
        ['openFeedback', snapshot.workspace.open_feedback],
      ] as const
    : []

  return (
    <div className="flex flex-1 flex-col gap-6 p-4 sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <ServerCog className="size-5 text-primary" />
            <h1 className="text-xl font-bold tracking-tight">{t('system.diagnostics.title')}</h1>
          </div>
          <p className="max-w-2xl text-sm text-muted-foreground">{t('system.diagnostics.description')}</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void loadSnapshot()} disabled={loading}>
          <RefreshCw className={`mr-2 size-4 ${loading ? 'animate-spin' : ''}`} />
          {t('system.diagnostics.refresh')}
        </Button>
      </div>

      {failed && !snapshot ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-destructive">{t('system.diagnostics.failed')}</CardContent>
        </Card>
      ) : snapshot ? (
        <>
          <Card>
            <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3">
                <span className={`size-3 rounded-full ${snapshot.overall_status === 'healthy' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                <div>
                  <p className="font-semibold">{t('system.diagnostics.liveSnapshot')}</p>
                  <p className="text-xs text-muted-foreground">
                    {new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'medium' }).format(new Date(snapshot.generated_at))}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge variant={snapshot.overall_status === 'healthy' ? 'success' : 'warning'}>
                  {t(`system.diagnostics.overall.${snapshot.overall_status}`)}
                </Badge>
                <Badge variant="outline">v{snapshot.version}</Badge>
                <Badge variant="outline">{snapshot.environment}</Badge>
              </div>
            </CardContent>
          </Card>

          <section className="space-y-3">
            <div>
              <h2 className="font-semibold">{t('system.diagnostics.sections.dependencies')}</h2>
              <p className="text-sm text-muted-foreground">{t('system.diagnostics.sections.dependenciesDescription')}</p>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {snapshot.dependencies.map((item) => <DependencyCard key={item.name} diagnostic={item} />)}
            </div>
          </section>

          <section className="space-y-3">
            <div>
              <h2 className="font-semibold">{t('system.diagnostics.sections.process')}</h2>
              <p className="text-sm text-muted-foreground">{t('system.diagnostics.sections.processDescription')}</p>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <Card>
                <CardHeader className="pb-2"><CardDescription>{t('system.diagnostics.process.uptime')}</CardDescription></CardHeader>
                <CardContent className="flex items-center gap-2 text-2xl font-bold"><Clock3 className="size-5 text-primary" />{formatDuration(snapshot.process.uptime_seconds)}</CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2"><CardDescription>{t('system.diagnostics.process.memory')}</CardDescription></CardHeader>
                <CardContent className="flex items-center gap-2 text-2xl font-bold"><MemoryStick className="size-5 text-primary" />{formatBytes(snapshot.process.rss_bytes)}</CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2"><CardDescription>{t('system.diagnostics.process.threads')}</CardDescription></CardHeader>
                <CardContent className="flex items-center gap-2 text-2xl font-bold"><Activity className="size-5 text-primary" />{snapshot.process.thread_count}</CardContent>
              </Card>
            </div>
          </section>

          <section className="space-y-3">
            <div>
              <h2 className="font-semibold">{t('system.diagnostics.sections.workspace')}</h2>
              <p className="text-sm text-muted-foreground">{t('system.diagnostics.sections.workspaceDescription')}</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {workspaceMetrics.map(([key, value]) => (
                <Card key={key}>
                  <CardContent className="flex items-center justify-between gap-4 p-4">
                    <span className="text-sm text-muted-foreground">{t(`system.diagnostics.workspace.${key}`)}</span>
                    <span className="text-xl font-bold tabular-nums">{value ?? '—'}</span>
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>
        </>
      ) : (
        <div className="py-16 text-center text-sm text-muted-foreground">{t('system.diagnostics.loading')}</div>
      )}
    </div>
  )
}
