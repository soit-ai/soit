import { useState } from 'react'

import { toast } from 'sonner'

import {
  ConsoleButton,
  ConsoleModal,
  DataStateRow,
  FilterChip,
  FilterSearch,
  IconPlus,
  Pager,
  StatTile,
  StatTileGrid,
  StatusChip,
  Workbench,
  WorkbenchPanel,
} from '../../components'
import { EvaluationImportField } from '../../components/evaluation-import-field'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui'
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import { catColor, compactNumber, percent, relativeTime } from '../../adapters/palette'
import { useSubjectNames } from '../../adapters/subject-names'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { getAgentWorkbench } from '@/services/agent-service'
import {
  createDataset,
  importDatasetCases,
  importLineErrors,
  listDatasets,
  type Dataset,
  type ImportLineError,
} from '@/services/evaluation-service'
import { requestErrorMessage } from '@/utils/request'

const EMPTY_FORM = { name: '', subject_id: '', description: '' }

/**
 * Observe › Evaluations: the datasets agents are evaluated against, with the
 * revision each is at and how its latest report went. Creating one can seed it
 * from a JSONL file in the same step.
 */
export default function ConsoleEvaluations() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const subjectName = useSubjectNames()
  const [status, setStatus] = useState<'active' | 'archived'>('active')
  const [search, setSearch] = useState('')
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [content, setContent] = useState('')
  const [lineErrors, setLineErrors] = useState<ImportLineError[]>([])
  // Set once the dataset exists, so retrying a failed import adds the cases to
  // it rather than creating the dataset a second time.
  const [createdId, setCreatedId] = useState<string | null>(null)

  const datasetsQuery = useQuery({
    queryKey: ['console', 'evaluations', 'datasets', status],
    queryFn: () => listDatasets({ status, limit: 200 }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const agentsQuery = useQuery({
    queryKey: ['console', 'evaluations', 'agents'],
    queryFn: () => getAgentWorkbench({ page_size: 100 }),
    options: { enabled: creating, retry: false, refetchOnWindowFocus: false },
  })
  const agents = agentsQuery.data?.items || []

  const all = datasetsQuery.data || []
  const needle = search.trim().toLowerCase()
  const rows = needle
    ? all.filter((row) =>
        [row.name, row.description, subjectName(row.subject_id)].some((value) =>
          value.toLowerCase().includes(needle),
        ),
      )
    : all

  const withReport = all.filter((row) => row.latest_report)
  const passing = withReport.filter((row) => row.latest_report?.passed).length

  const closeCreate = () => {
    setCreating(false)
    setForm(EMPTY_FORM)
    setContent('')
    setLineErrors([])
    setCreatedId(null)
  }

  const createMutation = useMutation<Dataset, unknown, void>({
    mutationKey: ['console', 'evaluations', 'create'],
    mutationFn: async () => {
      let dataset: Dataset | null = null
      let datasetId = createdId
      if (!datasetId) {
        dataset = await createDataset(
          {
            subject_id: form.subject_id,
            name: form.name.trim(),
            description: form.description.trim(),
          },
          { suppressErrorToast: true },
        )
        datasetId = dataset.id
        setCreatedId(datasetId)
      }
      if (content.trim()) {
        const result = await importDatasetCases(
          datasetId,
          { content, note: 'Imported when the dataset was created' },
          { suppressErrorToast: true },
        )
        dataset = result.dataset
      }
      return dataset as Dataset
    },
    onSuccess: (dataset) => {
      void datasetsQuery.refetch()
      toast.success(t('console.evaluations.create.created', { name: dataset.name }))
      closeCreate()
      navigate(`/observe/evaluations/${dataset.id}`)
    },
    onError: (error) => {
      void datasetsQuery.refetch()
      setLineErrors(importLineErrors(error))
      toast.error(requestErrorMessage(error, t('console.evaluations.create.failed')))
    },
  })

  return (
    <Workbench
      title={t('console.evaluations.title')}
      description={t('console.evaluations.description')}
      actions={
        <ConsoleButton
          variant="primary"
          onClick={() => {
            setForm(EMPTY_FORM)
            setCreating(true)
          }}
        >
          <IconPlus />
          {t('console.evaluations.newDataset')}
        </ConsoleButton>
      }
      tiles={
        <StatTileGrid>
          <StatTile
            label={t('console.evaluations.tiles.datasets')}
            value={datasetsQuery.data ? compactNumber(all.length) : '—'}
            na={!datasetsQuery.data}
          />
          <StatTile
            label={t('console.evaluations.tiles.cases')}
            value={
              datasetsQuery.data
                ? compactNumber(all.reduce((sum, row) => sum + row.case_count, 0))
                : '—'
            }
            na={!datasetsQuery.data}
          />
          <StatTile
            label={t('console.evaluations.tiles.passing')}
            value={withReport.length ? `${passing} / ${withReport.length}` : '—'}
            na={!withReport.length}
            sub={<span className="mono dimmer">{t('console.evaluations.tiles.passingSub')}</span>}
          />
          <StatTile
            label={t('console.evaluations.tiles.neverRun')}
            value={datasetsQuery.data ? String(all.length - withReport.length) : '—'}
            na={!datasetsQuery.data}
            sub={<span className="mono dimmer">{t('console.evaluations.tiles.neverRunSub')}</span>}
          />
        </StatTileGrid>
      }
      filters={
        <>
          <FilterChip active={status === 'active'} onClick={() => setStatus('active')}>
            {t('console.evaluations.filters.active')}
          </FilterChip>
          <FilterChip active={status === 'archived'} onClick={() => setStatus('archived')}>
            {t('console.evaluations.filters.archived')}
          </FilterChip>
          <FilterSearch
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t('console.evaluations.filters.searchPlaceholder')}
            aria-label={t('console.evaluations.filters.searchPlaceholder')}
            className="max-w-[340px]"
          />
        </>
      }
    >
      <WorkbenchPanel>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('console.evaluations.columns.dataset')}</TableHead>
              <TableHead>{t('console.evaluations.columns.agent')}</TableHead>
              <TableHead className="num">{t('console.evaluations.columns.revision')}</TableHead>
              <TableHead className="num">{t('console.evaluations.columns.cases')}</TableHead>
              <TableHead>{t('console.evaluations.columns.latest')}</TableHead>
              <TableHead className="num">{t('console.evaluations.columns.updated')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 ? (
              <DataStateRow
                colSpan={6}
                isPending={datasetsQuery.isPending}
                isError={datasetsQuery.isError}
                emptyLabel={t('console.evaluations.empty')}
              />
            ) : (
              rows.map((row) => {
                const latest = row.latest_report
                return (
                  <TableRow
                    key={row.id}
                    className="rowlink cursor-pointer"
                    onClick={() => navigate(`/observe/evaluations/${row.id}`)}
                  >
                    <TableCell>
                      <b style={{ fontWeight: 600, overflowWrap: 'anywhere' }}>{row.name}</b>
                      {row.description && (
                        <>
                          <br />
                          <span className="dimmer" style={{ fontSize: 11 }}>
                            {row.description}
                          </span>
                        </>
                      )}
                    </TableCell>
                    <TableCell>
                      <span
                        className="idm"
                        style={{ '--c': catColor(row.subject_id) } as React.CSSProperties}
                      >
                        <i />
                        {subjectName(row.subject_id)}
                      </span>
                    </TableCell>
                    <TableCell className="num mono dim">r{row.revision}</TableCell>
                    <TableCell className="num dim">{row.case_count}</TableCell>
                    <TableCell>
                      {latest ? (
                        <>
                          <StatusChip status={latest.passed ? 'pass' : 'failed'} />{' '}
                          <span className="mono dim" style={{ fontSize: 11.5 }}>
                            {latest.passed_count}/{latest.total} · {percent(latest.pass_rate)}
                          </span>{' '}
                          <span className="mono dimmer" style={{ fontSize: 10.5, marginLeft: 6 }}>
                            {t('console.evaluations.ranRevision', {
                              revision: latest.dataset_revision,
                            })}
                            {latest.dataset_revision !== row.revision &&
                              ` · ${t('console.evaluations.outdated')}`}
                            {latest.model_ref && ` · ${latest.model_ref}`}
                          </span>
                        </>
                      ) : (
                        <span className="dimmer">{t('console.evaluations.neverRun')}</span>
                      )}
                    </TableCell>
                    <TableCell className="num dimmer">{relativeTime(row.updated_at)}</TableCell>
                  </TableRow>
                )
              })
            )}
          </TableBody>
        </Table>
        <Pager summary={t('console.evaluations.pagerNote')} />
      </WorkbenchPanel>

      <ConsoleModal
        open={creating}
        onOpenChange={(open) => (open ? setCreating(true) : closeCreate())}
        title={t('console.evaluations.create.title')}
        note={t('console.evaluations.create.note')}
        confirmLabel={
          createdId ? t('console.evaluations.create.importOnly') : t('console.common.create')
        }
        confirmDisabled={createdId ? !content.trim() : !form.name.trim() || !form.subject_id}
        busy={createMutation.isPending}
        onConfirm={() => createMutation.mutate(undefined)}
      >
        <div className="mrow">
          <label htmlFor="evaluation-agent">{t('console.evaluations.create.agent')}</label>
          <select
            id="evaluation-agent"
            className="input"
            value={form.subject_id}
            disabled={Boolean(createdId)}
            onChange={(event) => setForm((state) => ({ ...state, subject_id: event.target.value }))}
          >
            <option value="">{t('console.evaluations.create.agentPlaceholder')}</option>
            {agents.map((agent) => (
              <option key={agent.id} value={agent.id}>
                {agent.name}
              </option>
            ))}
          </select>
        </div>
        <div className="mrow">
          <label htmlFor="evaluation-name">
            {t('console.evaluations.create.name')}
            <small>{t('console.evaluations.create.nameHint')}</small>
          </label>
          <input
            id="evaluation-name"
            className="input"
            value={form.name}
            disabled={Boolean(createdId)}
            onChange={(event) => setForm((state) => ({ ...state, name: event.target.value }))}
          />
        </div>
        <div className="mrow">
          <label htmlFor="evaluation-description">
            {t('console.evaluations.create.description')}
          </label>
          <input
            id="evaluation-description"
            className="input"
            value={form.description}
            disabled={Boolean(createdId)}
            onChange={(event) =>
              setForm((state) => ({ ...state, description: event.target.value }))
            }
          />
        </div>
        <EvaluationImportField content={content} onContent={setContent} errors={lineErrors} />
      </ConsoleModal>
    </Workbench>
  )
}
