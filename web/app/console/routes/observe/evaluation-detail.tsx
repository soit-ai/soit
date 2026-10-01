import { useState } from 'react'

import { useParams } from 'react-router'
import { toast } from 'sonner'

import {
  Backlink,
  ConsoleButton,
  ConsoleModal,
  ConsoleTabs,
  DataStateNote,
  StatTile,
  StatTileGrid,
  StatusChip,
  type ConsoleTabItem,
} from '../../components'
import { EvaluationCasesPanel } from '../../components/evaluation-cases-panel'
import { EvaluationImportField } from '../../components/evaluation-import-field'
import { EvaluationReportsPanel } from '../../components/evaluation-reports-panel'
import { EvaluationVersionsPanel } from '../../components/evaluation-versions-panel'
import { catColor, percent, relativeTime } from '../../adapters/palette'
import { useSubjectNames } from '../../adapters/subject-names'
import { useRefreshEvaluations } from '../../adapters/use-refresh-evaluations'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import {
  exportDatasetCases,
  getDataset,
  importDatasetCases,
  importLineErrors,
  runEvaluation,
  updateDataset,
  type Dataset,
  type ImportLineError,
  type RegressionReport,
} from '@/services/evaluation-service'
import { requestErrorMessage } from '@/utils/request'

type Tab = 'cases' | 'reports' | 'versions'

const EMPTY_RUN = { version: '', model: '', maxCases: '50' }

/**
 * Observe › Evaluations › one dataset: its cases, the reports of running them
 * and the versions it has been through. "Run evaluation" runs every active case
 * on the agent now and opens the report it records.
 */
export default function ConsoleEvaluationDetail() {
  const { t } = useTranslation()
  const { datasetId } = useParams<{ datasetId: string }>()
  const subjectName = useSubjectNames()
  const refresh = useRefreshEvaluations()

  const [tab, setTab] = useState<Tab>('cases')
  const [reportId, setReportId] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [run, setRun] = useState(EMPTY_RUN)
  const [importing, setImporting] = useState(false)
  const [content, setContent] = useState('')
  const [lineErrors, setLineErrors] = useState<ImportLineError[]>([])
  const [archiving, setArchiving] = useState(false)

  const datasetQuery = useQuery({
    queryKey: ['console', 'evaluations', 'dataset', datasetId],
    queryFn: () => getDataset(datasetId as string, { suppressErrorToast: true }),
    options: { enabled: Boolean(datasetId), retry: false, refetchOnWindowFocus: false },
  })
  const dataset = datasetQuery.data

  const onWriteError = (fallback: string) => (error: unknown) => {
    toast.error(requestErrorMessage(error, fallback))
  }

  const maxCases = Number(run.maxCases)
  const runValid = Number.isInteger(maxCases) && maxCases >= 1 && maxCases <= 200

  const runMutation = useMutation<RegressionReport, unknown, Dataset>({
    mutationKey: ['console', 'evaluations', 'run'],
    mutationFn: (target) =>
      runEvaluation(
        {
          subject_id: target.subject_id,
          dataset: target.name,
          max_cases: maxCases,
          ...(run.version.trim() ? { subject_version_id: run.version.trim() } : {}),
          ...(run.model.trim() ? { model_ref: run.model.trim() } : {}),
        },
        { suppressErrorToast: true },
      ),
    onSuccess: (report) => {
      void refresh()
      setRunning(false)
      setTab('reports')
      setReportId(report.id)
      toast.success(
        t('console.evaluations.run.done', {
          passed: report.summary_json.passed ?? 0,
          total: report.summary_json.total ?? 0,
        }),
      )
    },
    onError: onWriteError(t('console.evaluations.run.failed')),
  })

  const importMutation = useMutation<{ imported: number }, unknown, string>({
    mutationKey: ['console', 'evaluations', 'import'],
    mutationFn: (id) => importDatasetCases(id, { content }, { suppressErrorToast: true }),
    onSuccess: (result) => {
      void refresh()
      setImporting(false)
      setContent('')
      setLineErrors([])
      setTab('cases')
      toast.success(t('console.evaluations.import.done', { count: result.imported }))
    },
    onError: (error) => {
      setLineErrors(importLineErrors(error))
      toast.error(requestErrorMessage(error, t('console.evaluations.import.failed')))
    },
  })

  const exportMutation = useMutation<string, unknown, Dataset>({
    mutationKey: ['console', 'evaluations', 'export'],
    mutationFn: (target) => exportDatasetCases(target.id, target.name),
    onSuccess: (filename) => toast.success(t('console.common.exported', { filename })),
    onError: onWriteError(t('console.evaluations.export.failed')),
  })

  const statusMutation = useMutation<
    unknown,
    unknown,
    { id: string; status: 'active' | 'archived' }
  >({
    mutationKey: ['console', 'evaluations', 'status'],
    mutationFn: ({ id, status }) => updateDataset(id, { status }, { suppressErrorToast: true }),
    onSuccess: () => {
      void refresh()
      setArchiving(false)
    },
    onError: onWriteError(t('console.evaluations.archive.failed')),
  })

  if (!dataset) {
    return (
      <>
        <Backlink to="/observe/evaluations">{t('console.evaluations.back')}</Backlink>
        <div className="rd-head">
          <h1>{t('console.evaluations.title')}</h1>
        </div>
        <div className="panel">
          <DataStateNote isPending={datasetQuery.isPending} isError={datasetQuery.isError} />
        </div>
      </>
    )
  }

  const archived = dataset.status === 'archived'
  const latest = dataset.latest_report
  const tabs: ConsoleTabItem<Tab>[] = [
    { id: 'cases', label: t('console.evaluations.tabs.cases'), count: dataset.case_count },
    { id: 'reports', label: t('console.evaluations.tabs.reports') },
    { id: 'versions', label: t('console.evaluations.tabs.versions') },
  ]

  return (
    <>
      <Backlink to="/observe/evaluations">{t('console.evaluations.back')}</Backlink>

      <div className="rd-head">
        <h1 style={{ overflowWrap: 'anywhere' }}>{dataset.name}</h1>
        <span className="chip">r{dataset.revision}</span>
        {archived && <StatusChip status="disabled" label={t('console.evaluations.archived')} />}
        <span className="chip">
          <i style={{ background: catColor(dataset.subject_id) }} />
          {subjectName(dataset.subject_id)}
        </span>
        <span className="spacer" />
        <ConsoleButton
          onClick={() => exportMutation.mutate(dataset)}
          disabled={exportMutation.isPending}
        >
          {t('console.evaluations.export.action')}
        </ConsoleButton>
        {!archived && (
          <ConsoleButton
            onClick={() => {
              setContent('')
              setLineErrors([])
              setImporting(true)
            }}
          >
            {t('console.evaluations.import.action')}
          </ConsoleButton>
        )}
        {archived ? (
          <ConsoleButton
            onClick={() => statusMutation.mutate({ id: dataset.id, status: 'active' })}
            disabled={statusMutation.isPending}
          >
            {t('console.evaluations.archive.restore')}
          </ConsoleButton>
        ) : (
          <ConsoleButton onClick={() => setArchiving(true)}>
            {t('console.evaluations.archive.action')}
          </ConsoleButton>
        )}
        <ConsoleButton
          variant="primary"
          disabled={archived || dataset.case_count === 0}
          title={dataset.case_count === 0 ? t('console.evaluations.run.noCases') : undefined}
          onClick={() => {
            setRun(EMPTY_RUN)
            setRunning(true)
          }}
        >
          {t('console.evaluations.run.action')}
        </ConsoleButton>
      </div>
      {dataset.description && (
        <p className="dim" style={{ fontSize: 12.5, margin: '2px 0 14px' }}>
          {dataset.description}
        </p>
      )}

      <StatTileGrid>
        <StatTile label={t('console.evaluations.tiles.cases')} value={String(dataset.case_count)} />
        <StatTile
          label={t('console.evaluations.tiles.revision')}
          value={`r${dataset.revision}`}
          sub={
            <span className="mono dimmer">
              {t('console.evaluations.tiles.changed', { when: relativeTime(dataset.updated_at) })}
            </span>
          }
        />
        <StatTile
          label={t('console.evaluations.tiles.latestRate')}
          value={latest ? percent(latest.pass_rate) : '—'}
          na={!latest}
          sub={
            latest ? (
              <span className="mono dimmer">
                {latest.passed_count}/{latest.total}
                {latest.dataset_revision !== dataset.revision &&
                  ` · ${t('console.evaluations.outdated')}`}
              </span>
            ) : (
              <span className="mono dimmer">{t('console.evaluations.neverRun')}</span>
            )
          }
        />
        <StatTile
          label={t('console.evaluations.tiles.lastRun')}
          value={latest ? relativeTime(latest.created_at) : '—'}
          na={!latest}
          sub={
            latest ? <span className="mono dimmer">{latest.subject_version_id}</span> : undefined
          }
        />
      </StatTileGrid>

      <ConsoleTabs items={tabs} value={tab} onChange={setTab} />

      {tab === 'cases' && <EvaluationCasesPanel dataset={dataset} />}
      {tab === 'reports' && (
        <EvaluationReportsPanel dataset={dataset} selectedId={reportId} onSelect={setReportId} />
      )}
      {tab === 'versions' && <EvaluationVersionsPanel dataset={dataset} />}

      <ConsoleModal
        open={running}
        onOpenChange={setRunning}
        title={t('console.evaluations.run.title')}
        note={t('console.evaluations.run.note', { count: dataset.case_count })}
        confirmLabel={t('console.evaluations.run.confirm')}
        confirmDisabled={!runValid}
        busy={runMutation.isPending}
        onConfirm={() => runMutation.mutate(dataset)}
      >
        <div className="mrow">
          <label htmlFor="evaluation-run-version">
            {t('console.evaluations.run.version')}
            <small>{t('console.evaluations.run.versionHint')}</small>
          </label>
          <input
            id="evaluation-run-version"
            className="input"
            value={run.version}
            style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
            onChange={(event) => setRun((state) => ({ ...state, version: event.target.value }))}
          />
        </div>
        <div className="mrow">
          <label htmlFor="evaluation-run-model">
            {t('console.evaluations.run.model')}
            <small>{t('console.evaluations.run.modelHint')}</small>
          </label>
          <input
            id="evaluation-run-model"
            className="input"
            value={run.model}
            style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
            onChange={(event) => setRun((state) => ({ ...state, model: event.target.value }))}
          />
        </div>
        <div className="mrow">
          <label htmlFor="evaluation-run-max">
            {t('console.evaluations.run.maxCases')}
            <small>{t('console.evaluations.run.maxCasesHint')}</small>
          </label>
          <input
            id="evaluation-run-max"
            className="input"
            inputMode="numeric"
            value={run.maxCases}
            onChange={(event) => setRun((state) => ({ ...state, maxCases: event.target.value }))}
          />
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={importing}
        onOpenChange={setImporting}
        title={t('console.evaluations.import.title')}
        note={t('console.evaluations.import.note')}
        confirmLabel={t('console.evaluations.import.confirm')}
        confirmDisabled={!content.trim()}
        busy={importMutation.isPending}
        onConfirm={() => importMutation.mutate(dataset.id)}
      >
        <EvaluationImportField
          content={content}
          onContent={setContent}
          errors={lineErrors}
          required
        />
      </ConsoleModal>

      <ConsoleModal
        open={archiving}
        onOpenChange={setArchiving}
        title={t('console.evaluations.archive.title')}
        note={dataset.name}
        confirmLabel={t('console.evaluations.archive.action')}
        destructive
        busy={statusMutation.isPending}
        onConfirm={() => statusMutation.mutate({ id: dataset.id, status: 'archived' })}
      >
        <div className="mrow">
          <span className="dim" style={{ fontSize: 12 }}>
            {t('console.evaluations.archive.note')}
          </span>
        </div>
      </ConsoleModal>
    </>
  )
}
