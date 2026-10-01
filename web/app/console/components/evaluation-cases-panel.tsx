import { useEffect, useState } from 'react'

import { toast } from 'sonner'

import { ConsoleButton } from './button'
import { DataStateRow } from './data-state'
import { FilterSearch, Seg } from './filters'
import { IconPlus } from './icons'
import { ConsoleModal } from './modal'
import { Pager } from './pager'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui'
import { WorkbenchPanel } from './workbench'
import {
  EMPTY_CASE_FORM,
  caseToForm,
  formToCase,
  inputPreview,
  type CaseFormError,
  type CaseFormState,
} from '../adapters/evaluations'
import { useRefreshEvaluations } from '../adapters/use-refresh-evaluations'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import {
  addDatasetCase,
  listDatasetCases,
  removeDatasetCase,
  updateDatasetCase,
  type Dataset,
  type DatasetCase,
  type ExpectedFeatures,
} from '@/services/evaluation-service'
import { requestErrorMessage } from '@/utils/request'

const PAGE_SIZE = 25
const INPUT_MODES: CaseFormState['inputMode'][] = ['text', 'json']

/** What a case asserts, one chip per expectation. */
export function ExpectationChips({ features }: { features: ExpectedFeatures }) {
  const { t } = useTranslation()
  const chips: string[] = []
  const terms = features.minimum_output_terms?.length
  if (terms) chips.push(t('console.evaluations.expect.terms', { count: terms }))
  if (features.max_latency_ms != null) {
    chips.push(t('console.evaluations.expect.latency', { value: features.max_latency_ms }))
  }
  if (features.max_cost_amount != null) {
    chips.push(t('console.evaluations.expect.cost', { value: features.max_cost_amount }))
  }
  if (features.llm_judge) {
    chips.push(
      t('console.evaluations.expect.judge', { value: features.llm_judge.min_score ?? 0.7 }),
    )
  }
  if (!chips.length) return <span className="dimmer">—</span>
  return (
    <span style={{ display: 'inline-flex', gap: 4, flexWrap: 'wrap' }}>
      {chips.map((chip) => (
        <span key={chip} className="chip">
          {chip}
        </span>
      ))}
    </span>
  )
}

/**
 * The Cases tab: a dataset's active cases, with the editor for adding and
 * changing one. Every write advances the dataset's revision, so the page
 * refetches the dataset, its versions and this list together.
 */
export function EvaluationCasesPanel({ dataset }: { dataset: Dataset }) {
  const { t } = useTranslation()
  const refresh = useRefreshEvaluations()
  const writable = dataset.status === 'active'

  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [tokens, setTokens] = useState<Array<string | undefined>>([undefined])
  const [editing, setEditing] = useState<DatasetCase | 'new' | null>(null)
  const [form, setForm] = useState<CaseFormState>(EMPTY_CASE_FORM)
  const [formError, setFormError] = useState<CaseFormError | null>(null)
  const [removing, setRemoving] = useState<DatasetCase | null>(null)

  // A search restarts the paging, and waits for a pause in typing.
  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(search.trim())
      setTokens([undefined])
    }, 250)
    return () => clearTimeout(timer)
  }, [search])

  const page = tokens.length - 1
  const casesQuery = useQuery({
    queryKey: ['console', 'evaluations', 'cases', dataset.id, query, page, tokens[page] ?? null],
    queryFn: () =>
      listDatasetCases(
        dataset.id,
        { q: query || undefined, page_token: tokens[page], page_size: PAGE_SIZE, with_total: true },
        { suppressErrorToast: true },
      ),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const cases = casesQuery.data?.items || []
  const total = casesQuery.data?.total
  const nextToken = casesQuery.data?.next_page_token

  const openEditor = (target: DatasetCase | 'new') => {
    setForm(target === 'new' ? EMPTY_CASE_FORM : caseToForm(target))
    setFormError(null)
    setEditing(target)
  }

  const onWriteError = (fallback: string) => (error: unknown) => {
    toast.error(requestErrorMessage(error, fallback))
  }

  const saveMutation = useMutation<DatasetCase, unknown, void>({
    mutationKey: ['console', 'evaluations', 'case-save'],
    mutationFn: () => {
      const built = formToCase(form)
      if (!built.ok) return Promise.reject(new CaseFormFailure(built.error))
      setFormError(null)
      return editing === 'new' || editing === null
        ? addDatasetCase(dataset.id, built.value, { suppressErrorToast: true })
        : updateDatasetCase(dataset.id, editing.id, built.value, { suppressErrorToast: true })
    },
    onSuccess: () => {
      void refresh()
      setEditing(null)
    },
    onError: (error) => {
      // A form that failed the local checks says why beside the field; only a
      // refusal from the server is a toast.
      if (error instanceof CaseFormFailure) setFormError(error.code)
      else onWriteError(t('console.evaluations.cases.saveFailed'))(error)
    },
  })

  const removeMutation = useMutation<unknown, unknown, DatasetCase>({
    mutationKey: ['console', 'evaluations', 'case-remove'],
    mutationFn: (item) => removeDatasetCase(dataset.id, item.id, { suppressErrorToast: true }),
    onSuccess: () => {
      void refresh()
      setRemoving(null)
    },
    onError: onWriteError(t('console.evaluations.cases.removeFailed')),
  })

  const set = <K extends keyof CaseFormState>(key: K, value: CaseFormState[K]) =>
    setForm((state) => ({ ...state, [key]: value }))

  return (
    <WorkbenchPanel
      title={t('console.evaluations.cases.title')}
      hint={t('console.evaluations.cases.hint')}
      actions={
        <>
          <FilterSearch
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t('console.evaluations.cases.searchPlaceholder')}
            aria-label={t('console.evaluations.cases.searchPlaceholder')}
            style={{ maxWidth: 220, minWidth: 0, flex: '1 1 120px' }}
          />
          {writable && (
            <ConsoleButton
              variant="primary"
              size="sm"
              style={{ whiteSpace: 'nowrap' }}
              onClick={() => openEditor('new')}
            >
              <IconPlus />
              {t('console.evaluations.cases.add')}
            </ConsoleButton>
          )}
        </>
      }
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t('console.evaluations.cases.columns.name')}</TableHead>
            <TableHead>{t('console.evaluations.cases.columns.input')}</TableHead>
            <TableHead>{t('console.evaluations.cases.columns.expects')}</TableHead>
            <TableHead className="num">{t('console.evaluations.cases.columns.revision')}</TableHead>
            <TableHead className="num" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {cases.length === 0 ? (
            <DataStateRow
              colSpan={5}
              isPending={casesQuery.isPending}
              isError={casesQuery.isError}
              emptyLabel={t(
                query ? 'console.evaluations.cases.noMatch' : 'console.evaluations.cases.empty',
              )}
            />
          ) : (
            cases.map((item) => (
              <TableRow key={item.id}>
                <TableCell style={{ overflowWrap: 'anywhere' }}>
                  <b style={{ fontWeight: 600 }}>{item.name}</b>
                  {item.source_run_id && (
                    <>
                      <br />
                      <span className="mono dimmer" style={{ fontSize: 10.5 }}>
                        {t('console.evaluations.cases.fromRun', { run: item.source_run_id })}
                      </span>
                    </>
                  )}
                </TableCell>
                <TableCell
                  className="mono dim"
                  style={{ fontSize: 11, maxWidth: 360, overflowWrap: 'anywhere' }}
                >
                  {inputPreview(item.input)}
                </TableCell>
                <TableCell>
                  <ExpectationChips features={item.expected_features_json} />
                </TableCell>
                <TableCell className="num mono dim">r{item.dataset_revision}</TableCell>
                <TableCell className="num">
                  {writable && (
                    <span style={{ display: 'inline-flex', gap: 6 }}>
                      <ConsoleButton
                        variant="ghost"
                        style={{ height: 22, fontSize: 10.5 }}
                        onClick={() => openEditor(item)}
                      >
                        {t('console.evaluations.cases.edit')}
                      </ConsoleButton>
                      <ConsoleButton
                        variant="ghost"
                        style={{ height: 22, fontSize: 10.5, color: 'var(--danger-foreground)' }}
                        onClick={() => setRemoving(item)}
                      >
                        {t('console.common.delete')}
                      </ConsoleButton>
                    </span>
                  )}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
      <Pager
        summary={
          total != null
            ? t('console.evaluations.cases.pageSummary', {
                from: cases.length ? page * PAGE_SIZE + 1 : 0,
                to: page * PAGE_SIZE + cases.length,
                total,
              })
            : undefined
        }
        onPrev={page > 0 ? () => setTokens((state) => state.slice(0, -1)) : undefined}
        onNext={nextToken ? () => setTokens((state) => [...state, nextToken as string]) : undefined}
      />

      <ConsoleModal
        open={editing !== null}
        onOpenChange={(open) => {
          if (!open) setEditing(null)
        }}
        title={
          editing === 'new'
            ? t('console.evaluations.cases.addTitle')
            : t('console.evaluations.cases.editTitle')
        }
        note={t('console.evaluations.cases.formNote')}
        confirmLabel={t('console.common.save')}
        confirmDisabled={!form.name.trim()}
        busy={saveMutation.isPending}
        onConfirm={() => saveMutation.mutate(undefined)}
      >
        <div className="mrow">
          <label htmlFor="evaluation-case-name">{t('console.evaluations.cases.fields.name')}</label>
          <input
            id="evaluation-case-name"
            className="input"
            value={form.name}
            onChange={(event) => set('name', event.target.value)}
          />
        </div>
        <div className="mrow">
          <label htmlFor="evaluation-case-input">
            {t('console.evaluations.cases.fields.input')}
            <small>{t('console.evaluations.cases.fields.inputHint')}</small>
          </label>
          <div style={{ display: 'grid', gap: 6 }}>
            <Seg<CaseFormState['inputMode']>
              options={INPUT_MODES.map((mode) => ({
                value: mode,
                label: t(
                  `console.evaluations.cases.fields.input${mode === 'text' ? 'Text' : 'Json'}`,
                ),
              }))}
              value={form.inputMode}
              onChange={(mode) => set('inputMode', mode)}
            />
            <textarea
              id="evaluation-case-input"
              className="input"
              rows={5}
              spellCheck={false}
              value={form.input}
              onChange={(event) => set('input', event.target.value)}
            />
          </div>
        </div>
        <div className="mrow">
          <label htmlFor="evaluation-case-terms">
            {t('console.evaluations.cases.fields.terms')}
            <small>{t('console.evaluations.cases.fields.termsHint')}</small>
          </label>
          <textarea
            id="evaluation-case-terms"
            className="input"
            rows={3}
            value={form.terms}
            onChange={(event) => set('terms', event.target.value)}
          />
        </div>
        <div className="mrow">
          <label htmlFor="evaluation-case-latency">
            {t('console.evaluations.cases.fields.maxLatency')}
          </label>
          <input
            id="evaluation-case-latency"
            className="input"
            inputMode="numeric"
            value={form.maxLatency}
            onChange={(event) => set('maxLatency', event.target.value)}
          />
        </div>
        <div className="mrow">
          <label htmlFor="evaluation-case-cost">
            {t('console.evaluations.cases.fields.maxCost')}
          </label>
          <input
            id="evaluation-case-cost"
            className="input"
            inputMode="decimal"
            value={form.maxCost}
            onChange={(event) => set('maxCost', event.target.value)}
          />
        </div>
        <div className="mrow">
          <label htmlFor="evaluation-case-judge">
            {t('console.evaluations.cases.fields.judge')}
            <small>{t('console.evaluations.cases.fields.judgeHint')}</small>
          </label>
          <div style={{ display: 'grid', gap: 6 }}>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 12.5 }}>
              <input
                id="evaluation-case-judge"
                type="checkbox"
                checked={form.judge}
                onChange={(event) => set('judge', event.target.checked)}
              />
              {t('console.evaluations.cases.fields.judgeOn')}
            </label>
            {form.judge && (
              <>
                <textarea
                  className="input"
                  rows={3}
                  aria-label={t('console.evaluations.cases.fields.rubric')}
                  placeholder={t('console.evaluations.cases.fields.rubric')}
                  value={form.rubric}
                  onChange={(event) => set('rubric', event.target.value)}
                />
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <input
                    className="input"
                    style={{ flex: '1 1 110px' }}
                    inputMode="decimal"
                    aria-label={t('console.evaluations.cases.fields.minScore')}
                    placeholder={t('console.evaluations.cases.fields.minScore')}
                    value={form.minScore}
                    onChange={(event) => set('minScore', event.target.value)}
                  />
                  <input
                    className="input"
                    style={{ flex: '2 1 180px', fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
                    aria-label={t('console.evaluations.cases.fields.judgeModel')}
                    placeholder={t('console.evaluations.cases.fields.judgeModel')}
                    value={form.judgeModel}
                    onChange={(event) => set('judgeModel', event.target.value)}
                  />
                </div>
              </>
            )}
          </div>
        </div>
        {formError && (
          <div className="mrow">
            <span />
            <span role="alert" style={{ color: 'var(--danger-foreground)', fontSize: 12 }}>
              {t(`console.evaluations.cases.errors.${formError}`)}
            </span>
          </div>
        )}
      </ConsoleModal>

      <ConsoleModal
        open={Boolean(removing)}
        onOpenChange={(open) => {
          if (!open) setRemoving(null)
        }}
        title={t('console.evaluations.cases.removeTitle')}
        note={removing?.name || ''}
        confirmLabel={t('console.common.delete')}
        destructive
        busy={removeMutation.isPending}
        onConfirm={() => removing && removeMutation.mutate(removing)}
      >
        <div className="mrow">
          <span className="dim" style={{ fontSize: 12 }}>
            {t('console.evaluations.cases.removeNote')}
          </span>
        </div>
      </ConsoleModal>
    </WorkbenchPanel>
  )
}

/** A form that fails the checks made before anything is sent. */
class CaseFormFailure extends Error {
  constructor(readonly code: CaseFormError) {
    super(code)
  }
}
