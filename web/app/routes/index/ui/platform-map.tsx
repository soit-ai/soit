import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useNavigate } from '@/hooks/use-navigate'
import { useTranslation } from '@/i18n'
import type { TranslationKey } from '@/i18n/types'

import { platformModules } from '../constants'
import { useHomeFormatters } from '../hooks/use-home-formatters'
import type { DashboardSummary } from '../hooks/use-home-dashboard'
import { PlatformRelationshipGraph, type PlatformGraphModule } from './platform-relationship-graph'

type PlatformMapProps = {
  summary: DashboardSummary
}

export function PlatformMap({ summary }: PlatformMapProps) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { formatNumber } = useHomeFormatters()

  const modules: PlatformGraphModule[] = platformModules.map((item) => ({
    ...item,
    title: t(`app.home.platform.modules.${item.key}.title` as TranslationKey),
    description: t(`app.home.platform.modules.${item.key}.description` as TranslationKey),
    value:
      item.key === 'knowledge' ||
      item.key === 'workflow' ||
      item.key === 'tasks' ||
      item.key === 'observability'
        ? t(`app.home.platform.modules.${item.key}.value` as TranslationKey, {
            count:
              item.key === 'knowledge'
                ? formatNumber(summary.knowledgeCount)
                : item.key === 'workflow'
                  ? formatNumber(summary.workflowCount)
                  : item.key === 'tasks'
                    ? formatNumber(summary.activeTaskCount)
                    : formatNumber(summary.runCount),
          })
        : t(`app.home.platform.modules.${item.key}.value` as TranslationKey),
  }))

  return (
    <Card className="overflow-hidden border-slate-200/70 bg-white/78 shadow-none backdrop-blur-sm dark:border-slate-800 dark:bg-slate-950/60">
      <CardHeader className="space-y-3 border-b border-slate-200/70 dark:border-slate-800">
        <div className="text-[11px] font-medium uppercase tracking-[0.28em] text-slate-500 dark:text-slate-400">
          {t('app.home.platform.eyebrow')}
        </div>
        <CardTitle className="text-2xl">{t('app.home.platform.title')}</CardTitle>
        <CardDescription>
          {t('app.home.platform.description')}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <PlatformRelationshipGraph
          summary={summary}
          modules={modules}
          relationEyebrow={t('app.home.platform.relationEyebrow')}
          relationDescription={t('app.home.platform.relationDescription')}
          coreLabel={t('app.home.platform.coreLabel')}
          coreTitle={t('app.home.platform.coreTitle')}
          coreDescription={t('app.home.platform.coreDescription')}
          publishedLabel={t('app.home.platform.published')}
          draftLabel={t('app.home.platform.draft')}
          onOpen={(href) => navigate(href)}
        />
      </CardContent>
    </Card>
  )
}
