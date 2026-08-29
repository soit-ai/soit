import { useMemo, useState } from 'react'

import { useSearchParams } from 'react-router'

import {
  ConsoleButton,
  FilterChip,
  FilterSearch,
  KeyValueList,
  KindChip,
  Pager,
  Seg,
  StatusChip,
  Workbench,
  WorkbenchPanel,
  runStatusToConsole,
  type ConsoleKind,
} from '../../components'
import { CONSOLE_KIND_COLOR } from '../../components/kind-chip'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui'
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import {
  getRunCostByDay,
  getRunCostByModel,
  getRunCostByProvider,
  getRunCostSummary,
  listRuns,
  type RunResponse,
} from '@/services/run-service'

const RANGES = ['1h', '24h', '7d', '30d'] as const
type RunRange = (typeof RANGES)[number]

const RANGE_MS: Record<RunRange, number> = {
  '1h': 3_600_000,
  '24h': 86_400_000,
  '7d': 7 * 86_400_000,
  '30d': 30 * 86_400_000,
}

type QuickStatus = 'all' | 'succeeded' | 'running' | 'failed'

const PAGE_SIZE = 20

function formatTokens(tokens: number): string {
  if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(1)}M`
  if (tokens >= 1_000) return `${(tokens / 1_000).toFixed(1)}k`
  return String(tokens)
}

function formatDuration(ms?: number | null): string {
  if (ms == null) return '—'
  if (ms >= 60_000) return `${(ms / 60_000).toFixed(1)}m`
  return `${(ms / 1000).toFixed(1)}s`
}

function formatStarted(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return `${date.toISOString().slice(11, 19)}Z`
}

function subjectKind(run: RunResponse): ConsoleKind {
  const kind = run.subject_kind || ''
  return (kind in CONSOLE_KIND_COLOR ? kind : 'agent') as ConsoleKind
}

export default function ConsoleRuns() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const range = (RANGES as readonly string[]).includes(searchParams.get('range') || '')
    ? (searchParams.get('range') as RunRange)
    : '24h'
  const quickStatus = (searchParams.get('status') as QuickStatus) || 'all'
  const mode = searchParams.get('mode') || 'all'
  const kind = searchParams.get('subject_kind') || 'all'
  const hasToolCall = searchParams.get('has_tool_call') === '1'
  const hasCitation = searchParams.get('has_citation') === '1'
  const hasAudit = searchParams.get('has_audit') === '1'
  const pageToken = searchParams.get('page_token') || undefined
  const [search, setSearch] = useState('')
  const [prevTokens, setPrevTokens] = useState<string[]>([])

  const patchParams = (patch: Record<string, string | null>, keepPage = false) => {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(patch)) {
      if (value == null || value === '' || value === 'all' || value === '0') next.delete(key)
      else next.set(key, value)
    }
    if (!keepPage) {
      next.delete('page_token')
      setPrevTokens([])
    }
    setSearchParams(next)
  }

  const startedAfter = useMemo(
    () => new Date(Date.now() - RANGE_MS[range]).toISOString(),
    // Refresh the window when any filter navigation happens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [range, searchParams.toString()],
  )

  const listParams = useMemo(
    () => ({
      status: quickStatus === 'all' ? undefined : quickStatus,
      mode: mode === 'all' ? undefined : mode,
      subject_kind: kind === 'all' ? undefined : kind,
      has_tool_call: hasToolCall || undefined,
      has_citation: hasCitation || undefined,
      has_audit: hasAudit || undefined,
      started_after: startedAfter,
      include_observe_summary: true,
      page_size: PAGE_SIZE,
      page_token: pageToken,
    }),
    [quickStatus, mode, kind, hasToolCall, hasCitation, hasAudit, startedAfter, pageToken],
  )

  const costParams = useMemo(
    () => ({
      status: listParams.status,
      mode: listParams.mode,
      subject_kind: listParams.subject_kind,
      started_after: startedAfter,
    }),
    [listParams.status, listParams.mode, listParams.subject_kind, startedAfter],
  )

  const runsQuery = useQuery({
    queryKey: ['console', 'runs', listParams],
    queryFn: () => listRuns(listParams),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const costSummaryQuery = useQuery({
    queryKey: ['console', 'runs', 'cost-summary', costParams],
    queryFn: () => getRunCostSummary(costParams),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const costByProviderQuery = useQuery({
    queryKey: ['console', 'runs', 'cost-provider', costParams],
    queryFn: () => getRunCostByProvider(costParams),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const costByModelQuery = useQuery({
    queryKey: ['console', 'runs', 'cost-model', costParams],
    queryFn: () => getRunCostByModel(costParams),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const costByDayParams = useMemo(
    () => ({ ...costParams, started_after: new Date(Date.now() - RANGE_MS['7d']).toISOString() }),
    [costParams],
  )
  const costByDayQuery = useQuery({
    queryKey: ['console', 'runs', 'cost-day', costByDayParams],
    queryFn: () => getRunCostByDay(costByDayParams),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const runs = runsQuery.data?.items || []
  const filteredRuns = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return runs
    return runs.filter((run) =>
      [run.id, run.subject_id, run.trace_id, run.mode]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query)),
    )
  }, [runs, search])

  const nextToken = runsQuery.data?.next_page_token || null

  const goNext = () => {
    if (!nextToken) return
    setPrevTokens((stack) => [...stack, pageToken || ''])
    patchParams({ page_token: nextToken }, true)
  }
  const goPrev = () => {
    if (prevTokens.length === 0) return
    const stack = [...prevTokens]
    const previous = stack.pop() || null
    setPrevTokens(stack)
    patchParams({ page_token: previous || null }, true)
  }

  const totalTokens = costSummaryQuery.data
    ? costSummaryQuery.data.tokens_prompt + costSummaryQuery.data.tokens_completion
    : null

  const costColumn = (
    rows: { key: string; tokens: number }[] | null | undefined,
    error: boolean,
  ) => {
    if (error) return [{ key: t('console.runs.cost.unavailable'), value: '—' }]
    if (!rows || rows.length === 0) return [{ key: t('console.runs.cost.empty'), value: '—' }]
    return rows.slice(0, 3).map((row) => ({
      key: row.key,
      value: t('console.runs.cost.tokens', { tokens: formatTokens(row.tokens) }),
    }))
  }

  return (
    <Workbench
      title={t('console.runs.title')}
      description={t('console.runs.description')}
      actions={
        <>
          <Seg
            options={RANGES}
            value={range}
            onChange={(value) => patchParams({ range: value })}
          />
          <ConsoleButton>{t('console.runs.export')}</ConsoleButton>
        </>
      }
      filters={
        <>
          {(
            [
              ['all', t('console.runs.filters.all')],
              ['succeeded', t('console.runs.filters.succeeded')],
              ['running', t('console.runs.filters.running')],
              ['failed', t('console.runs.filters.failed')],
            ] as const
          ).map(([value, label]) => (
            <FilterChip
              key={value}
              active={quickStatus === value}
              onClick={() => patchParams({ status: value === 'all' ? null : value })}
            >
              {label}
            </FilterChip>
          ))}
          <span
            aria-hidden
            style={{ width: 1, height: 18, background: 'var(--border)', margin: '0 2px' }}
          />
          <FilterChip
            active={hasToolCall}
            onClick={() => patchParams({ has_tool_call: hasToolCall ? null : '1' })}
          >
            {t('console.runs.filters.hasToolCalls')}
          </FilterChip>
          <FilterChip
            active={hasCitation}
            onClick={() => patchParams({ has_citation: hasCitation ? null : '1' })}
          >
            {t('console.runs.filters.hasCitations')}
          </FilterChip>
          <FilterChip
            active={hasAudit}
            onClick={() => patchParams({ has_audit: hasAudit ? null : '1' })}
          >
            {t('console.runs.filters.hasAudit')}
          </FilterChip>
          <Select value={mode} onValueChange={(value) => value != null && patchParams({ mode: value })}>
            <SelectTrigger size="sm" aria-label={t('console.runs.filters.mode')}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('console.runs.filters.modeAll')}</SelectItem>
              <SelectItem value="chat">chat</SelectItem>
              <SelectItem value="task">task</SelectItem>
              <SelectItem value="workflow">workflow</SelectItem>
              <SelectItem value="api">api</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={kind}
            onValueChange={(value) => value != null && patchParams({ subject_kind: value })}
          >
            <SelectTrigger size="sm" aria-label={t('console.runs.filters.subjectKind')}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('console.runs.filters.subjectKindAll')}</SelectItem>
              <SelectItem value="agent">agent</SelectItem>
              <SelectItem value="workflow">workflow</SelectItem>
              <SelectItem value="knowledge">knowledge</SelectItem>
            </SelectContent>
          </Select>
          <FilterSearch
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t('console.runs.filters.searchPlaceholder')}
          />
        </>
      }
    >
      <WorkbenchPanel
        className="mb-3"
        title={t('console.runs.cost.title')}
        hint={t('console.runs.cost.hint', { range })}
        actions={
          totalTokens != null && (
            <span className="more mono" style={{ fontSize: 11 }}>
              {t('console.runs.cost.tokens', { tokens: formatTokens(totalTokens) })}
              {costSummaryQuery.data?.request_count != null &&
                ` · ${costSummaryQuery.data.request_count} req`}
            </span>
          )
        }
      >
        <div className="costgrid">
          <div>
            <h3>{t('console.runs.cost.byProvider')}</h3>
            <KeyValueList
              items={costColumn(
                costByProviderQuery.data?.map((row) => ({
                  key: row.provider || '—',
                  tokens: row.tokens_prompt + row.tokens_completion,
                })),
                costByProviderQuery.isError,
              )}
            />
          </div>
          <div>
            <h3>{t('console.runs.cost.byModel')}</h3>
            <KeyValueList
              items={costColumn(
                costByModelQuery.data?.map((row) => ({
                  key: row.model_ref || '—',
                  tokens: row.tokens_prompt + row.tokens_completion,
                })),
                costByModelQuery.isError,
              )}
            />
          </div>
          <div>
            <h3>{t('console.runs.cost.byDay')}</h3>
            <KeyValueList
              items={costColumn(
                costByDayQuery.data
                  ?.slice(-3)
                  .reverse()
                  .map((row) => ({
                    key: row.date,
                    tokens: row.tokens_prompt + row.tokens_completion,
                  })),
                costByDayQuery.isError,
              )}
            />
          </div>
        </div>
      </WorkbenchPanel>

      <WorkbenchPanel>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('console.runs.columns.run')}</TableHead>
              <TableHead>{t('console.runs.columns.subject')}</TableHead>
              <TableHead>{t('console.runs.columns.mode')}</TableHead>
              <TableHead className="num">{t('console.runs.columns.observed')}</TableHead>
              <TableHead className="num">{t('console.runs.columns.audits')}</TableHead>
              <TableHead className="num">{t('console.runs.columns.duration')}</TableHead>
              <TableHead>{t('console.runs.columns.status')}</TableHead>
              <TableHead className="num">{t('console.runs.columns.started')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {runsQuery.isError ? (
              <TableRow>
                <TableCell colSpan={8}>
                  <div className="empty-note">{t('console.runs.loadError')}</div>
                </TableCell>
              </TableRow>
            ) : filteredRuns.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8}>
                  <div className="empty-note">
                    {runsQuery.isPending ? t('console.common.loading') : t('console.runs.empty')}
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              filteredRuns.map((run) => (
                <TableRow
                  key={run.id}
                  className={cn('rowlink cursor-pointer')}
                  onClick={() => navigate(`/observe/runs/${run.id}`)}
                >
                  <TableCell>
                    <span className="runid">{run.id}</span>
                  </TableCell>
                  <TableCell>
                    <KindChip kind={subjectKind(run)} label={run.subject_id || '—'} />
                  </TableCell>
                  <TableCell className="dim">{run.mode}</TableCell>
                  <TableCell className="num dim">
                    {run.observe_summary?.step_count ?? '—'}
                  </TableCell>
                  <TableCell className="num">
                    <span className="mono dimmer">{run.observe_summary?.audit_count ?? '—'}</span>
                  </TableCell>
                  <TableCell className="num dim">{formatDuration(run.duration_ms)}</TableCell>
                  <TableCell>
                    <StatusChip status={runStatusToConsole(run.status)} />
                  </TableCell>
                  <TableCell className="num dimmer">{formatStarted(run.started_at)}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
        <Pager
          summary={t('console.runs.pageSummary', { count: filteredRuns.length })}
          onPrev={goPrev}
          onNext={goNext}
          prevDisabled={prevTokens.length === 0}
          nextDisabled={!nextToken}
          prevLabel={t('console.runs.prev')}
          nextLabel={t('console.runs.next')}
        />
      </WorkbenchPanel>
    </Workbench>
  )
}
