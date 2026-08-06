import { ArrowRight, Building2, KeyRound, LockKeyhole, ShieldCheck, Users } from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useTranslation } from '@/i18n'
import { useNavigate } from '@/hooks/use-navigate'
import { useQuery } from '@/hooks/use-query'
import { listApiKeys } from '@/services/api-key-service'
import { getCurrentUser, getWorkspace, listWorkspaceMembers } from '@/services/identity-service'
import { getWorkspaceUsagePolicy } from '@/services/security-service'
import { listSecrets } from '@/services/secrets-service'
import { formatDateTime, isoToZonedDate } from '@/utils/date-time'

const formatTimestamp = (value?: string | null) => {
  if (!value) {
    return '-'
  }
  return formatDateTime(isoToZonedDate(value))
}

function SettingsOverviewPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const { data: currentUser } = useQuery({
    queryKey: ['settings', 'current-user'],
    queryFn: () => getCurrentUser(),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const workspaceId = currentUser?.workspace_id || ''

  const { data: workspace } = useQuery({
    queryKey: ['settings', 'workspace', workspaceId],
    queryFn: () => getWorkspace(workspaceId),
    options: {
      enabled: Boolean(workspaceId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const { data: members = [] } = useQuery({
    queryKey: ['settings', 'members', workspaceId],
    queryFn: () => listWorkspaceMembers(workspaceId),
    options: {
      enabled: Boolean(workspaceId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const { data: apiKeyPage } = useQuery({
    queryKey: ['settings', 'api-keys'],
    queryFn: () => listApiKeys({ page_size: 100 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const { data: usagePolicy } = useQuery({
    queryKey: ['settings', 'usage-policy'],
    queryFn: () => getWorkspaceUsagePolicy(),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const { data: secrets = [] } = useQuery({
    queryKey: ['settings', 'secrets'],
    queryFn: () => listSecrets({ limit: 200, offset: 0 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const activeApiKeys = (apiKeyPage?.items || []).filter((item) => item.status === 'active')
  const latestSecret = [...secrets].sort((left, right) => right.updated_at.localeCompare(left.updated_at))[0]

  const quickActions = [
    {
      title: t('system.settings.overview.controlSurface.team.title'),
      description: t('system.settings.overview.controlSurface.team.description'),
      href: '/settings/team',
      icon: Users,
    },
    {
      title: t('system.settings.overview.controlSurface.api.title'),
      description: t('system.settings.overview.controlSurface.api.description'),
      href: '/settings/api',
      icon: KeyRound,
    },
    {
      title: t('system.settings.overview.controlSurface.secrets.title'),
      description: t('system.settings.overview.controlSurface.secrets.description'),
      href: '/settings/secrets',
      icon: LockKeyhole,
    },
    {
      title: t('system.settings.overview.controlSurface.security.title'),
      description: t('system.settings.overview.controlSurface.security.description'),
      href: '/settings/security',
      icon: ShieldCheck,
    },
  ]

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <Card className="border-none bg-gradient-to-br from-zinc-950 via-slate-900 to-sky-900 text-white shadow-xl">
        <CardHeader className="gap-4">
          <Badge variant="secondary" className="w-fit bg-white/10 text-white hover:bg-white/10">
            {t('system.settings.overview.badge')}
          </Badge>
          <div className="space-y-2">
            <CardTitle className="text-3xl font-semibold tracking-tight">
              {workspace?.name || t('system.settings.overview.fallbackTitle')}
            </CardTitle>
            <CardDescription className="max-w-2xl text-slate-300">
              {workspace?.description || t('system.settings.overview.fallbackDescription')}
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="grid gap-3 lg:grid-cols-4">
          <button
            type="button"
            onClick={() => navigate('/settings/team')}
            className="rounded-2xl border border-white/10 bg-white/5 p-4 text-left transition-colors hover:bg-white/10"
          >
            <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-white/10">
              <Building2 className="h-5 w-5" />
            </div>
            <div className="text-sm text-slate-300">{t('system.settings.overview.stats.workspaceRole')}</div>
            <div className="mt-1 text-lg font-medium">{currentUser?.workspace_role || '-'}</div>
          </button>
          <button
            type="button"
            onClick={() => navigate('/settings/team')}
            className="rounded-2xl border border-white/10 bg-white/5 p-4 text-left transition-colors hover:bg-white/10"
          >
            <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-white/10">
              <Users className="h-5 w-5" />
            </div>
            <div className="text-sm text-slate-300">{t('system.settings.overview.stats.members')}</div>
            <div className="mt-1 text-lg font-medium">{members.length}</div>
          </button>
          <button
            type="button"
            onClick={() => navigate('/settings/api')}
            className="rounded-2xl border border-white/10 bg-white/5 p-4 text-left transition-colors hover:bg-white/10"
          >
            <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-white/10">
              <KeyRound className="h-5 w-5" />
            </div>
            <div className="text-sm text-slate-300">{t('system.settings.overview.stats.activeApiKeys')}</div>
            <div className="mt-1 text-lg font-medium">{activeApiKeys.length}</div>
          </button>
          <button
            type="button"
            onClick={() => navigate('/settings/secrets')}
            className="rounded-2xl border border-white/10 bg-white/5 p-4 text-left transition-colors hover:bg-white/10"
          >
            <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-white/10">
              <LockKeyhole className="h-5 w-5" />
            </div>
            <div className="text-sm text-slate-300">{t('system.settings.overview.stats.secrets')}</div>
            <div className="mt-1 text-lg font-medium">{secrets.length}</div>
          </button>
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardHeader>
            <CardTitle>{t('system.settings.overview.controlSurface.title')}</CardTitle>
            <CardDescription>{t('system.settings.overview.controlSurface.description')}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2">
            {quickActions.map((action) => (
              <button
                key={action.title}
                type="button"
                onClick={() => navigate(action.href)}
                className="rounded-2xl border p-4 text-left transition-colors hover:border-primary/40"
              >
                <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-muted">
                  <action.icon className="h-5 w-5" />
                </div>
                <div className="text-sm font-medium">{action.title}</div>
                <div className="mt-1 text-sm text-muted-foreground">{action.description}</div>
                <div className="mt-4 inline-flex items-center text-sm font-medium text-primary">
                  {t('system.settings.overview.controlSurface.open')}
                  <ArrowRight className="ml-2 h-4 w-4" />
                </div>
              </button>
            ))}
          </CardContent>
        </Card>

        <div className="grid gap-4">
          <Card>
            <CardHeader>
              <CardTitle>{t('system.settings.overview.identity.title')}</CardTitle>
              <CardDescription>{t('system.settings.overview.identity.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">{t('system.settings.overview.identity.workspaceId')}</span>
                <span className="font-medium">{workspace?.id || workspaceId || '-'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">{t('system.settings.overview.identity.tenantId')}</span>
                <span className="font-medium">{currentUser?.tenant_id || workspace?.tenant_id || '-'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">{t('system.settings.overview.identity.tenantRole')}</span>
                <span className="font-medium">{currentUser?.tenant_role || '-'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">{t('system.settings.overview.identity.created')}</span>
                <span className="font-medium">{formatTimestamp(workspace?.created_at)}</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t('system.settings.overview.limits.title')}</CardTitle>
              <CardDescription>{t('system.settings.overview.limits.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">{t('system.settings.overview.limits.llmPerMinute')}</span>
                <span className="font-medium">{usagePolicy?.llm_rate_limit_per_minute ?? '-'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">{t('system.settings.overview.limits.toolPerMinute')}</span>
                <span className="font-medium">{usagePolicy?.tool_rate_limit_per_minute ?? '-'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">{t('system.settings.overview.limits.llmDailyQuota')}</span>
                <span className="font-medium">{usagePolicy?.llm_daily_quota ?? '-'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">{t('system.settings.overview.limits.toolDailyQuota')}</span>
                <span className="font-medium">{usagePolicy?.tool_daily_quota ?? '-'}</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t('system.settings.overview.secretsHealth.title')}</CardTitle>
              <CardDescription>{t('system.settings.overview.secretsHealth.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">{t('system.settings.overview.secretsHealth.total')}</span>
                <span className="font-medium">{secrets.length}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">{t('system.settings.overview.secretsHealth.latestRotated')}</span>
                <span className="font-medium">{formatTimestamp(latestSecret?.last_rotated_at || latestSecret?.updated_at)}</span>
              </div>
              <Button variant="outline" className="w-full" onClick={() => navigate('/settings/secrets')}>
                {t('system.settings.overview.secretsHealth.manage')}
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

export default SettingsOverviewPage
