import { StatTile, StatusChip } from '../../components'
import { relativeTime } from '../../adapters/palette'
import { useDiagnosticsQuery, useMembersQuery, useSettingsIdentity } from './shared'
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import type { TFunction } from '@/i18n/types'
import { getCreditBalance, listCreditEntries } from '@/services/billing-service'
import type { EditionDiagnostic } from '@/services/diagnostics-service'

/**
 * Credits arrive as fixed-point decimal strings ("612.400000"). `magnitude`
 * drops the sign, for totals the label already says are consumption.
 */
function formatCredits(value: string, magnitude = false): string {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return value
  return (magnitude ? Math.abs(parsed) : parsed).toLocaleString('en-US', {
    maximumFractionDigits: 2,
  })
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

/** What the licence grants, for the billing tiles: a Community deployment
 *  needs none, and an Enterprise one shows how long its licence has left. */
function licenceLine(edition: EditionDiagnostic | undefined, t: TFunction): string {
  if (!edition) return t('console.common.loading')
  if (edition.license_status === 'active') {
    return t('console.settings.billingPane.seatsLicensed', {
      license: edition.license_id,
      days: edition.days_left ?? 0,
    })
  }
  if (edition.license_status === 'absent') return t('console.settings.billingPane.editionCommunity')
  return t('console.settings.billingPane.editionUnlicensed', { reason: edition.reason ?? edition.license_status })
}

/** Seats are the workspace's members: a licence carries no seat cap. */
function seatsLine(edition: EditionDiagnostic | undefined, t: TFunction): string {
  if (edition?.license_status === 'active') return licenceLine(edition, t)
  return t('console.settings.billingPane.seatsCommunity')
}

/**
 * Edition and seats read the licence the runtime reports and the member
 * list; the credits ledger is the only billing surface and backs the spend
 * tile and the entries table. Invoicing belongs to SOIT Cloud, so Community
 * has none.
 */
export function BillingPane() {
  const { t } = useTranslation()
  const { workspaceId } = useSettingsIdentity(true)
  const membersQuery = useMembersQuery(workspaceId)
  // Read from the cache only: the About pane is the one that fetches it.
  const diagnostics = useDiagnosticsQuery(false).data

  // Credits are the only billing object the platform stores; the seat count
  // reuses the member list rather than inventing a licence record.
  const balanceQuery = useQuery({
    queryKey: ['console', 'settings', 'credit-balance'],
    queryFn: () => getCreditBalance(),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const entriesQuery = useQuery({
    queryKey: ['console', 'settings', 'credit-entries'],
    queryFn: () => listCreditEntries({ limit: 20 }),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const members = membersQuery.data || []

  const creditEntries = entriesQuery.data || []

  return (
    <>
      <div className="tiles cols-3">
        <StatTile
          label={t('console.settings.billingPane.edition')}
          value={diagnostics?.edition ? capitalize(diagnostics.edition.edition) : '—'}
          na={!diagnostics?.edition}
          sub={<span className="mono dimmer">{licenceLine(diagnostics?.edition, t)}</span>}
        />
        <StatTile
          label={t('console.settings.billingPane.seats')}
          value={membersQuery.data ? String(members.length) : '—'}
          na={!membersQuery.data}
          sub={<span className="mono dimmer">{seatsLine(diagnostics?.edition, t)}</span>}
        />
        <StatTile
          label={t('console.settings.billingPane.spend')}
          value={
            balanceQuery.data
              ? `${formatCredits(balanceQuery.data.deducted_total, true)} cr`
              : '—'
          }
          na={!balanceQuery.data}
          sub={
            <span className="mono dimmer">
              {balanceQuery.data
                ? `balance ${formatCredits(balanceQuery.data.balance)} cr`
                : t('console.common.loading')}
            </span>
          }
        />
      </div>
      <div className="panel">
        <div className="panel-head">
          <h2>{t('console.settings.billingPane.invoices')}</h2>
          <span className="hint">{t('console.settings.billingPane.invoicesHint')}</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>{t('console.settings.billingPane.columns.invoice')}</th>
              <th>{t('console.settings.billingPane.columns.period')}</th>
              <th className="num">{t('console.settings.billingPane.columns.amount')}</th>
              <th>{t('console.settings.billingPane.columns.status')}</th>
              <th className="num" />
            </tr>
          </thead>
          <tbody>
            {creditEntries.length === 0 ? (
              <tr>
                <td colSpan={5}>
                  <div className="empty-note">
                    {entriesQuery.isPending
                      ? t('console.common.loading')
                      : entriesQuery.isError
                        ? t('console.common.loadError')
                        : t('console.common.empty')}
                  </div>
                </td>
              </tr>
            ) : (
              creditEntries.map((entry) => (
                <tr key={entry.id}>
                  <td className="mono">{entry.id}</td>
                  <td className="dim">{entry.note || entry.cost_entry_id || entry.kind}</td>
                  <td className="num dim">{formatCredits(entry.credits_delta)} cr</td>
                  <td>
                    <StatusChip
                      status={entry.kind === 'grant' ? 'pass' : 'info'}
                      label={entry.kind.toUpperCase()}
                    />
                  </td>
                  <td className="num dimmer">{relativeTime(entry.created_at)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        <div className="pager">
          <span>{t('console.settings.billingPane.note')}</span>
        </div>
      </div>
    </>
  )
}
