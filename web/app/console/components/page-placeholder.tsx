import { Construction } from 'lucide-react'

import { useTranslation } from '@/i18n'
import type { TranslationKey } from '@/i18n/types'

import { EmptyState } from './empty-state'
import { Workbench } from './workbench'

/**
 * Skeleton screen for routes whose real implementation lands in a later
 * phase of the console rebuild. Keeps every pillar navigable from P1 on.
 */
export function PagePlaceholder({ titleKey }: { titleKey: TranslationKey }) {
  const { t } = useTranslation()

  return (
    <Workbench title={t(titleKey)}>
      <EmptyState
        icon={Construction}
        title={t(titleKey)}
        description={t('console.placeholder.description')}
      />
    </Workbench>
  )
}
