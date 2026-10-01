import { useState } from 'react'

import { ConsoleButton } from './button'
import { DataStateNote, DataStateRow } from './data-state'
import { KeyValueList } from './kv'
import { Pager } from './pager'
import { StatusChip } from './status-chip'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui'
import { WorkbenchPanel } from './workbench'
import { latency, percent, relativeTime } from '../adapters/palette'
import { useConsoleNavigate } from '../shell/use-console-navigate'
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import {
  getRegressionTrend,
  getReport,
  listReports,
  type Dataset,
  type RegressionCaseResult,
  type RegressionReport,
  type RegressionReportSummary,
  type RegressionTrendPoint,
} from '@/services/evaluation-service'

const PAGE_SIZE = 10
const TREND_POINTS = 20

const rate = (passed?: number, total?: number) =>
  total ? percent(passed != null ? passed / total : null) : '—'

/**
 * Pass rate per report, oldest to newest. A bar is a report: its height is its
 * pass rate and its colour whether it passed outright; a report on another
 * model is greyed, since it measured that model. Revisions are marked where
 * they change, because a bar on a different set of cases is not comparable to
 * the one beside it.
 */
function TrendBars({
  points,
  selectedId,
  onSelect,
}: {
  points: RegressionTrendPoint[]
  selectedId: string | null
  onSelect: (reportId: string) => void
}) {
  const { t } = useTranslation()
  if (!points.length) return null
  return (
    <div
      role="list"
      aria-label={t('console.evaluations.reports.trend')}
      style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 64, padding: '4px 14px 0' }}
    >
      {points.map((point, index) => {
        const changed = index > 0 && points[index - 1].dataset_revision !== point.dataset_revision
        return (
          <button
            key={point.report_id}
            type="button"
            role="listitem"
            title={t('console.evaluations.reports.trendPoint', {
              rate: percent(point.pass_rate),
              revision: point.dataset_revision,
              when: relativeTime(point.created_at),
            })}
            onClick={() => onSelect(point.report_id)}
            style={{
              flex: '1 1 0',
              maxWidth: 28,
              minWidth: 6,
              height: `${Math.max(6, Math.round((point.pass_rate ?? 0) * 100))}%`,
              border: 0,
              padding: 0,
              borderRadius: 2,
              cursor: 'pointer',
              background: point.passed ? 'var(--success-foreground)' : 'var(--danger-foreground)',
              opacity: selectedId === point.report_id ? 1 : 0.55,
              marginLeft: changed ? 8 : 0,
              outline: selectedId === point.report_id ? '1px solid var(--foreground)' : 'none',
            }}
          />
        )
      })}
    </div>
  )
}

function CaseRow({ result, report }: { result: RegressionCaseResult; report: RegressionReport }) {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const regressed = report.regressed_case_ids_json.includes(result.case_id)
  const fixed = report.fixed_case_ids_json.includes(result.case_id)
  const reasons = result.failure_reasons || []
  return (
    <TableRow>
      <TableCell style={{ overflowWrap: 'anywhere' }}>
        <b style={{ fontWeight: 600 }}>{result.name}</b>
      </TableCell>
      <TableCell>
        <StatusChip status={result.passed ? 'pass' : 'failed'} />
        {regressed && (
          <>
            {' '}
            <StatusChip status="blocked" label={t('console.evaluations.reports.regressed')} />
          </>
        )}
        {fixed && (
          <>
            {' '}
            <StatusChip status="info" label={t('console.evaluations.reports.fixed')} />
          </>
        )}
      </TableCell>
      <TableCell className="mono dim" style={{ fontSize: 11, overflowWrap: 'anywhere' }}>
        {reasons.length ? reasons.join(' · ') : <span className="dimmer">—</span>}
        {result.judge?.score != null && (
          <>
            <br />
            <span className="dimmer">
              {t('console.evaluations.reports.judgeScore', {
                score: result.judge.score,
                min: result.judge.min_score ?? 0.7,
              })}
            </span>
          </>
        )}
      </TableCell>
      <TableCell className="num dim">{latency(result.latency_ms)}</TableCell>
      <TableCell className="num">
        {result.run_id ? (
          <a
            className="runid"
            href={`/observe/runs/${result.run_id}`}
            onClick={(event) => {
              event.preventDefault()
              navigate(`/observe/runs/${result.run_id}`)
            }}
          >
            {result.run_id}
          </a>
        ) : (
          <span className="dimmer">—</span>
        )}
      </TableCell>
    </TableRow>
  )
}

/** One report: how it ran, what it was compared to, and every case's result. */
function ReportDetail({
  reportId,
  onSelect,
}: {
  reportId: string
  onSelect: (reportId: string) => void
}) {
  const { t } = useTranslation()
  const reportQuery = useQuery({
    queryKey: ['console', 'evaluations', 'report', reportId],
    queryFn: () => getReport(reportId, { suppressErrorToast: true }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const report = reportQuery.data

  if (!report) {
    return (
      <WorkbenchPanel title={t('console.evaluations.reports.detail')}>
        <DataStateNote isPending={reportQuery.isPending} isError={reportQuery.isError} />
      </WorkbenchPanel>
    )
  }
  const summary = report.summary_json
  return (
    <WorkbenchPanel
      title={t('console.evaluations.reports.detail')}
      hint={<span className="mono">{report.id}</span>}
    >
      <div style={{ padding: '4px 14px 10px' }}>
        <KeyValueList
          items={[
            {
              key: t('console.evaluations.reports.kv.result'),
              value: (
                <StatusChip
                  status={report.passed ? 'pass' : 'failed'}
                  label={`${summary.passed ?? 0}/${summary.total ?? 0}`}
                />
              ),
            },
            { key: t('console.evaluations.reports.kv.version'), value: report.subject_version_id },
            {
              key: t('console.evaluations.reports.kv.revision'),
              value: `${report.dataset} · r${report.dataset_revision}`,
            },
            {
              key: t('console.evaluations.reports.kv.baseline'),
              value: report.baseline_report_id ? (
                <button
                  type="button"
                  className="runid"
                  style={{ background: 'none', border: 0, padding: 0, cursor: 'pointer' }}
                  onClick={() => onSelect(report.baseline_report_id as string)}
                >
                  {report.baseline_report_id}
                </button>
              ) : (
                t('console.evaluations.reports.noBaseline')
              ),
            },
            ...(summary.model_ref
              ? [{ key: t('console.evaluations.reports.kv.model'), value: summary.model_ref }]
              : []),
            {
              key: t('console.evaluations.reports.kv.latency'),
              value: latency(report.metrics_json.avg_latency_ms),
            },
            {
              key: t('console.evaluations.reports.kv.cost'),
              value:
                report.metrics_json.total_cost_amount != null
                  ? String(report.metrics_json.total_cost_amount)
                  : '—',
            },
            {
              key: t('console.evaluations.reports.kv.changes'),
              value: t('console.evaluations.reports.changes', {
                regressed: report.regressed_case_ids_json.length,
                fixed: report.fixed_case_ids_json.length,
              }),
            },
          ]}
        />
        {summary.model_ref && (
          <p className="dim" style={{ fontSize: 11.5, margin: '8px 0 0' }}>
            {t('console.evaluations.reports.modelNote')}
          </p>
        )}
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t('console.evaluations.reports.columns.case')}</TableHead>
            <TableHead>{t('console.evaluations.reports.columns.result')}</TableHead>
            <TableHead>{t('console.evaluations.reports.columns.reasons')}</TableHead>
            <TableHead className="num">
              {t('console.evaluations.reports.columns.latency')}
            </TableHead>
            <TableHead className="num">{t('console.evaluations.reports.columns.run')}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {report.case_results_json.length === 0 ? (
            <DataStateRow colSpan={5} emptyLabel={t('console.evaluations.reports.noCases')} />
          ) : (
            report.case_results_json.map((result) => (
              <CaseRow key={result.case_id} result={result} report={report} />
            ))
          )}
        </TableBody>
      </Table>
    </WorkbenchPanel>
  )
}

/**
 * The Reports tab: how the dataset's evaluations have gone over time, and, for
 * the one picked, which cases regressed or were fixed against its baseline.
 */
export function EvaluationReportsPanel({
  dataset,
  selectedId,
  onSelect,
}: {
  dataset: Dataset
  selectedId: string | null
  onSelect: (reportId: string | null) => void
}) {
  const { t } = useTranslation()
  const [tokens, setTokens] = useState<Array<string | undefined>>([undefined])
  const page = tokens.length - 1

  const trendQuery = useQuery({
    queryKey: ['console', 'evaluations', 'trend', dataset.id, dataset.name],
    queryFn: () =>
      getRegressionTrend(
        {
          subject_kind: dataset.subject_kind,
          subject_id: dataset.subject_id,
          dataset: dataset.name,
          limit: TREND_POINTS,
        },
        { suppressErrorToast: true },
      ),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const reportsQuery = useQuery({
    queryKey: ['console', 'evaluations', 'reports', dataset.id, page, tokens[page] ?? null],
    queryFn: () =>
      listReports(
        {
          subject_kind: dataset.subject_kind,
          subject_id: dataset.subject_id,
          dataset: dataset.name,
          page_token: tokens[page],
          page_size: PAGE_SIZE,
          with_total: true,
        },
        { suppressErrorToast: true },
      ),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const reports: RegressionReportSummary[] = reportsQuery.data?.items || []
  const total = reportsQuery.data?.total
  const nextToken = reportsQuery.data?.next_page_token

  return (
    <>
      <WorkbenchPanel
        title={t('console.evaluations.reports.title')}
        hint={t('console.evaluations.reports.hint')}
      >
        <TrendBars
          points={trendQuery.data?.points || []}
          selectedId={selectedId}
          onSelect={onSelect}
        />
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('console.evaluations.reports.columns.when')}</TableHead>
              <TableHead>{t('console.evaluations.reports.columns.version')}</TableHead>
              <TableHead className="num">
                {t('console.evaluations.reports.columns.revision')}
              </TableHead>
              <TableHead>{t('console.evaluations.reports.columns.result')}</TableHead>
              <TableHead className="num">
                {t('console.evaluations.reports.columns.changes')}
              </TableHead>
              <TableHead className="num">
                {t('console.evaluations.reports.columns.latency')}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {reports.length === 0 ? (
              <DataStateRow
                colSpan={6}
                isPending={reportsQuery.isPending}
                isError={reportsQuery.isError}
                emptyLabel={t('console.evaluations.reports.empty')}
              />
            ) : (
              reports.map((report) => (
                <TableRow
                  key={report.id}
                  className="rowlink cursor-pointer"
                  data-selected={report.id === selectedId || undefined}
                  onClick={() => onSelect(report.id)}
                >
                  <TableCell className="dim">{relativeTime(report.created_at)}</TableCell>
                  <TableCell className="mono dim" style={{ overflowWrap: 'anywhere' }}>
                    {report.subject_version_id}
                    {report.summary_json.model_ref && (
                      <>
                        <br />
                        <span className="dimmer" style={{ fontSize: 10.5 }}>
                          {report.summary_json.model_ref}
                        </span>
                      </>
                    )}
                  </TableCell>
                  <TableCell className="num mono dim">r{report.dataset_revision}</TableCell>
                  <TableCell>
                    <StatusChip status={report.passed ? 'pass' : 'failed'} />{' '}
                    <span className="mono dim" style={{ fontSize: 11.5 }}>
                      {report.summary_json.passed ?? 0}/{report.summary_json.total ?? 0} ·{' '}
                      {rate(report.summary_json.passed, report.summary_json.total)}
                    </span>
                  </TableCell>
                  <TableCell className="num mono dim" style={{ fontSize: 11.5 }}>
                    {report.baseline_report_id
                      ? t('console.evaluations.reports.changes', {
                          regressed: report.regressed_case_ids_json.length,
                          fixed: report.fixed_case_ids_json.length,
                        })
                      : '—'}
                  </TableCell>
                  <TableCell className="num dim">
                    {latency(report.metrics_json.avg_latency_ms)}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
        <Pager
          summary={
            total != null
              ? t('console.evaluations.reports.pageSummary', {
                  from: reports.length ? page * PAGE_SIZE + 1 : 0,
                  to: page * PAGE_SIZE + reports.length,
                  total,
                })
              : undefined
          }
          onPrev={page > 0 ? () => setTokens((state) => state.slice(0, -1)) : undefined}
          onNext={
            nextToken ? () => setTokens((state) => [...state, nextToken as string]) : undefined
          }
        >
          {selectedId && (
            <ConsoleButton size="sm" variant="ghost" onClick={() => onSelect(null)}>
              {t('console.evaluations.reports.close')}
            </ConsoleButton>
          )}
        </Pager>
      </WorkbenchPanel>
      {selectedId && <ReportDetail reportId={selectedId} onSelect={onSelect} />}
    </>
  )
}
