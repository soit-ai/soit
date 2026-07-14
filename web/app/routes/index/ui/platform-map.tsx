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
    title: t(`agent.home.platform.modules.${item.key}.title` as TranslationKey),
    description: t(`agent.home.platform.modules.${item.key}.description` as TranslationKey),
    value:
      item.key === 'knowledge' ||
      item.key === 'workflow' ||
      item.key === 'tasks' ||
      item.key === 'observe'
        ? t(`agent.home.platform.modules.${item.key}.value` as TranslationKey, {
            count:
              item.key === 'knowledge'
                ? formatNumber(summary.knowledgeCount)
                : item.key === 'workflow'
                  ? formatNumber(summary.workflowCount)
                  : item.key === 'tasks'
                    ? formatNumber(summary.activeTaskCount)
                    : formatNumber(summary.runCount),
          })
        : t(`agent.home.platform.modules.${item.key}.value` as TranslationKey),
  }))

  return (
    <Card className="overflow-hidden">
      <CardHeader className="space-y-3 border-b border-border/70">
        <div className="text-[11px] font-medium uppercase tracking-[0.28em] text-muted-foreground">
          {t('agent.home.platform.eyebrow')}
        </div>
        <CardTitle className="text-2xl">{t('agent.home.platform.title')}</CardTitle>
        <CardDescription>
          {t('agent.home.platform.description')}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <PlatformRelationshipGraph
          summary={summary}
          modules={modules}
          relationEyebrow={t('agent.home.platform.relationEyebrow')}
          relationDescription={t('agent.home.platform.relationDescription')}
          coreLabel={t('agent.home.platform.coreLabel')}
          coreTitle={t('agent.home.platform.coreTitle')}
          coreDescription={t('agent.home.platform.coreDescription')}
          publishedLabel={t('agent.home.platform.published')}
          draftLabel={t('agent.home.platform.draft')}
          onOpen={(href) => navigate(href)}
        />
      </CardContent>
    </Card>
  )
}

