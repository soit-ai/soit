import { LayoutDashboard } from 'lucide-react'

import { useTranslation } from '@/i18n'

import { EmptyState, StatTile, StatTileGrid, Workbench } from '../components'

export default function ConsoleOverview() {
  const { t } = useTranslation()

  return (
    <Workbench
      title={t('console.overview.title')}
      description={t('console.overview.description')}
      tiles={
        <StatTileGrid>
          <StatTile label={t('console.status.running')} value="—" na />
          <StatTile label={t('console.status.pass')} value="—" na />
          <StatTile label={t('console.status.degraded')} value="—" na />
          <StatTile label={t('console.status.blocked')} value="—" na />
        </StatTileGrid>
      }
    >
      <EmptyState
        icon={LayoutDashboard}
        title={t('console.overview.emptyTitle')}
        description={t('console.overview.emptyDescription')}
      />
    </Workbench>
  )
}
