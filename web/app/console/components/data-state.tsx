import { useTranslation } from '@/i18n'

import { TableCell, TableRow } from './ui'

/**
 * The single loading / error / empty vocabulary for every wired console table.
 * Pages pass their query flags; the row renders the prototype `.empty-note`
 * so a table on live data reads exactly like one on fixtures.
 */
export interface DataStateProps {
  isPending?: boolean
  isError?: boolean
  /** Rendered when the query resolved with no rows. Defaults to the shared copy. */
  emptyLabel?: React.ReactNode
  /** Rendered when the query failed. Defaults to the shared copy. */
  errorLabel?: React.ReactNode
}

/** Resolves the message for a data state, or null when there is nothing to say. */
export function useDataStateLabel({
  isPending,
  isError,
  emptyLabel,
  errorLabel,
}: DataStateProps): React.ReactNode {
  const { t } = useTranslation()
  if (isError) return errorLabel ?? t('console.common.loadError')
  if (isPending) return t('console.common.loading')
  return emptyLabel ?? t('console.common.empty')
}

/** A full-width table row carrying the loading / error / empty note. */
export function DataStateRow({ colSpan, ...state }: DataStateProps & { colSpan: number }) {
  const label = useDataStateLabel(state)
  return (
    <TableRow>
      <TableCell colSpan={colSpan}>
        <div className="empty-note">{label}</div>
      </TableCell>
    </TableRow>
  )
}

/** The same note outside a table (card grids, rails, panels). */
export function DataStateNote({ className, ...state }: DataStateProps & { className?: string }) {
  const label = useDataStateLabel(state)
  return <div className={className ?? 'empty-note'}>{label}</div>
}
