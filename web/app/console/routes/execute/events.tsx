import { useMemo, useState } from 'react'

import { toast } from 'sonner'

import {
  ConsoleButton,
  DataStateRow,
  FilterChip,
  Pager,
  Seg,
  StatTile,
  StatTileGrid,
  StatusChip,
  Workbench,
  WorkbenchPanel,
} from '../../components'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui'
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import { catColor, relativeTime } from '../../adapters/palette'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import {
  listDeadLetters,
  redriveDeadLetter,
  type DeadLetterKind,
  type DeadLetterResponse,
} from '@/services/observe-service'
import { requestErrorMessage } from '@/utils/request'

const RANGES = ['1h', '24h', '7d'] as const

const KINDS: Array<DeadLetterKind | 'all'> = [
  'all',
  'response_interaction',
  'workflow_run',
  'task',
  'knowledge_ingest',
  'outbox_event',
]

/**
 * The runtime exposes no generic inbound-event feed; what it does record is the
 * dead-letter queue — every event that reached a terminal failure, with the
 * redrive path back into its original pipeline. That is what this screen shows.
 */
export default function ConsoleEvents() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [range, setRange] = useState<(typeof RANGES)[number]>('24h')
  const [kind, setKind] = useState<DeadLetterKind | 'all'>('all')
  const [redrivableOnly, setRedrivableOnly] = useState(false)
  const [redriven, setRedriven] = useState<Record<string, boolean>>({})

  const deadLettersQuery = useQuery({
    queryKey: ['console', 'dead-letters'],
    queryFn: () => listDeadLetters({ limit: 100 }),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const all = useMemo(() => deadLettersQuery.data || [], [deadLettersQuery.data])

  const redriveMutation = useMutation({
    mutationKey: ['console', 'dead-letters', 'redrive'],
    mutationFn: (entry: DeadLetterResponse) =>
      redriveDeadLetter(entry.kind, entry.id, { suppressErrorToast: true }),
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Redrive failed'))
    },
  })

  const rows = all.filter((row) => {
    if (kind !== 'all' && row.kind !== kind) return false
    if (redrivableOnly && !row.redrivable) return false
    return true
  })

  const countFor = (value: DeadLetterKind | 'all') =>
    value === 'all' ? all.length : all.filter((row) => row.kind === value).length

  const newest = useMemo(
    () =>
      all
        .map((row) => row.failed_at)
        .filter(Boolean)
        .sort()
        .reverse()[0],
    [all],
  )

  return (
    <Workbench
      title={t('console.events.title')}
      description={t('console.events.description')}
      actions={<Seg options={RANGES} value={range} onChange={setRange} />}
      tiles={
        <StatTileGrid>
          <StatTile
            label={t('console.deadLetters.tiles.total')}
            value={deadLettersQuery.data ? String(all.length) : '—'}
            na={!deadLettersQuery.data}
            sub={<span className="mono dimmer">after retry policy exhausted</span>}
          />
          <StatTile
            label={t('console.deadLetters.tiles.redrivable')}
            value={
              deadLettersQuery.data ? String(all.filter((row) => row.redrivable).length) : '—'
            }
            na={!deadLettersQuery.data}
            sub={<span className="mono dimmer">can re-enter the pipeline</span>}
          />
          <StatTile
            label={t('console.deadLetters.tiles.kinds')}
            value={
              deadLettersQuery.data ? String(new Set(all.map((row) => row.kind)).size) : '—'
            }
            na={!deadLettersQuery.data}
            sub={<span className="mono dimmer">distinct failure sources</span>}
          />
          <StatTile
            label={t('console.deadLetters.tiles.newest')}
            value={newest ? relativeTime(newest) : '—'}
            na={!newest}
            sub={<span className="mono dimmer">most recent terminal failure</span>}
          />
        </StatTileGrid>
      }
      filters={
        <>
          {KINDS.map((value) => (
            <FilterChip
              key={value}
              active={kind === value}
              count={countFor(value)}
              onClick={() => setKind(value)}
            >
              {t(`console.deadLetters.kinds.${value}` as 'console.deadLetters.kinds.all')}
            </FilterChip>
          ))}
          <FilterChip
            active={redrivableOnly}
            onClick={() => setRedrivableOnly((value) => !value)}
          >
            {t('console.deadLetters.redrivableOnly')}
          </FilterChip>
        </>
      }
    >
      <WorkbenchPanel>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('console.events.columns.event')}</TableHead>
              <TableHead>{t('console.events.columns.source')}</TableHead>
              <TableHead>{t('console.events.columns.type')}</TableHead>
              <TableHead>{t('console.events.columns.target')}</TableHead>
              <TableHead>{t('console.events.columns.decision')}</TableHead>
              <TableHead>{t('console.events.columns.run')}</TableHead>
              <TableHead className="num">{t('console.events.columns.received')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 ? (
              <DataStateRow
                colSpan={7}
                isPending={deadLettersQuery.isPending}
                isError={deadLettersQuery.isError}
                emptyLabel={t('console.deadLetters.empty')}
              />
            ) : (
              rows.map((row) => (
                <TableRow key={`${row.kind}:${row.id}`} className="rowlink">
                  <TableCell>
                    <span className="mono">{row.id}</span>
                  </TableCell>
                  <TableCell>
                    <span className="kind" style={{ '--c': catColor(row.kind) } as React.CSSProperties}>
                      <i />
                      {row.kind}
                    </span>
                  </TableCell>
                  <TableCell className="mono dim">{row.error_code || '—'}</TableCell>
                  <TableCell>
                    {row.subject ? (
                      <span className="idm" style={{ '--c': catColor(row.subject) } as React.CSSProperties}>
                        <i />
                        {row.subject}
                      </span>
                    ) : (
                      <span className="dimmer">{t('console.events.unresolved')}</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <StatusChip status="failed" label="FAILED" />
                    {row.error_message && (
                      <>
                        {' '}
                        <span className="dimmer" style={{ fontSize: 10.5 }}>
                          {row.error_message}
                        </span>
                      </>
                    )}
                  </TableCell>
                  <TableCell>
                    {row.run_id ? (
                      <a
                        className="runid"
                        href={`/observe/runs/${row.run_id}`}
                        onClick={(event) => {
                          event.preventDefault()
                          navigate(`/observe/runs/${row.run_id}`)
                        }}
                      >
                        {row.run_id}
                      </a>
                    ) : row.redrivable ? (
                      <ConsoleButton
                        size="sm"
                        disabled={redriveMutation.isPending || redriven[row.id]}
                        onClick={() =>
                          redriveMutation.mutate(row, {
                            onSuccess: () =>
                              setRedriven((state) => ({ ...state, [row.id]: true })),
                          })
                        }
                      >
                        {redriven[row.id]
                          ? t('console.deadLetters.redriven')
                          : t('console.deadLetters.redrive')}
                      </ConsoleButton>
                    ) : (
                      <span className="dimmer">—</span>
                    )}
                  </TableCell>
                  <TableCell className="num dimmer">{relativeTime(row.failed_at)}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
        <Pager summary={t('console.deadLetters.note')} />
      </WorkbenchPanel>
    </Workbench>
  )
}
