import { useState } from 'react'

import { toast } from 'sonner'

import { ConsoleButton } from './button'
import { DataStateRow } from './data-state'
import { ConsoleModal } from './modal'
import { Pager } from './pager'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui'
import type { VirtualModelTargetOption } from './virtual-models-panel'
import { WorkbenchPanel } from './workbench'
import { latency, relativeTime } from '../adapters/palette'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import {
  createModelReplay,
  getModelReplay,
  listModelReplays,
  type ModelReplay,
  type ModelReplaySide,
} from '@/services/evaluation-service'
import { requestErrorMessage } from '@/utils/request'

interface ReplayForm {
  modelRef: string
  dataset: string
  maxCases: string
}

const EMPTY_FORM: ReplayForm = { modelRef: '', dataset: '', maxCases: '50' }

const percent = (rate: number | null | undefined) =>
  rate == null ? '—' : `${Math.round(rate * 1000) / 10}%`

const amount = (value: number | null | undefined) =>
  value == null ? '—' : value.toFixed(value !== 0 && Math.abs(value) < 0.01 ? 6 : 4)

/** A change, signed, coloured by whether it is better (``higherIsBetter``). */
function Delta({
  value,
  format,
  higherIsBetter,
}: {
  value: number | null | undefined
  format: (value: number) => string
  higherIsBetter: boolean
}) {
  if (value == null || value === 0) return <span className="dimmer">±0</span>
  const better = higherIsBetter ? value > 0 : value < 0
  return (
    <span
      className="mono"
      style={{ color: better ? 'var(--success-foreground)' : 'var(--danger-foreground)' }}
    >
      {value > 0 ? '+' : '−'}
      {format(Math.abs(value))}
    </span>
  )
}

function Sides({
  before,
  after,
  format,
}: {
  before: ModelReplaySide
  after: ModelReplaySide
  format: (side: ModelReplaySide) => string
}) {
  return (
    <span className="mono" style={{ fontSize: 11.5 }}>
      {format(before)} <span className="dimmer">→</span> {format(after)}
    </span>
  )
}

/**
 * Build › Models › Regression replays: every agent's regression set run on a
 * candidate model next to the model it binds, before switching to it.
 */
export function ModelReplaysPanel({ options }: { options: VirtualModelTargetOption[] }) {
  const { t } = useTranslation()
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState<ReplayForm>(EMPTY_FORM)
  const [openId, setOpenId] = useState<string | null>(null)

  const replaysQuery = useQuery({
    queryKey: ['console', 'models', 'replays'],
    queryFn: () => listModelReplays({ suppressErrorToast: true }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const detailQuery = useQuery({
    queryKey: ['console', 'models', 'replays', openId],
    queryFn: () => getModelReplay(openId as string, { suppressErrorToast: true }),
    options: { retry: false, refetchOnWindowFocus: false, enabled: openId != null },
  })
  const replays = replaysQuery.data || []

  const maxCases = Number(form.maxCases)
  const formValid =
    Boolean(form.modelRef.trim()) && Number.isInteger(maxCases) && maxCases >= 1 && maxCases <= 200

  const createMutation = useMutation<ModelReplay, unknown, void>({
    mutationKey: ['console', 'models', 'replays', 'create'],
    mutationFn: () =>
      createModelReplay(
        {
          model_ref: form.modelRef.trim(),
          ...(form.dataset.trim() ? { dataset: form.dataset.trim() } : {}),
          max_cases: maxCases,
        },
        { suppressErrorToast: true },
      ),
    onSuccess: (replay) => {
      toast.success(
        t('console.modelReplays.done', {
          model: replay.model_ref,
          rate: percent(replay.totals.candidate.pass_rate),
        }),
      )
      setCreating(false)
      setForm(EMPTY_FORM)
      setOpenId(replay.id)
      void replaysQuery.refetch()
    },
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Failed to replay the regression sets'))
    },
  })

  const detail = openId != null ? detailQuery.data : undefined

  return (
    <WorkbenchPanel
      className="mt-3.5"
      title={t('console.modelReplays.title')}
      hint={t('console.modelReplays.hint')}
      actions={
        <ConsoleButton
          variant="primary"
          size="sm"
          style={{ whiteSpace: 'nowrap' }}
          onClick={() => {
            setForm(EMPTY_FORM)
            setCreating(true)
          }}
        >
          {t('console.modelReplays.create')}
        </ConsoleButton>
      }
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t('console.modelReplays.columns.model')}</TableHead>
            <TableHead className="num">{t('console.modelReplays.columns.cases')}</TableHead>
            <TableHead>{t('console.modelReplays.columns.passRate')}</TableHead>
            <TableHead className="num">{t('console.modelReplays.columns.latency')}</TableHead>
            <TableHead className="num">{t('console.modelReplays.columns.cost')}</TableHead>
            <TableHead className="num">{t('console.modelReplays.columns.changes')}</TableHead>
            <TableHead className="num">{t('console.modelReplays.columns.when')}</TableHead>
            <TableHead className="num" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {replays.length === 0 ? (
            <DataStateRow
              colSpan={8}
              isPending={replaysQuery.isPending}
              isError={replaysQuery.isError}
              emptyLabel={t('console.modelReplays.empty')}
            />
          ) : (
            replays.map((replay) => (
              <TableRow key={replay.id}>
                <TableCell>
                  <span className="mono" style={{ fontSize: 11.5 }}>
                    {replay.model_ref}
                  </span>
                </TableCell>
                <TableCell className="num">{replay.case_count}</TableCell>
                <TableCell>
                  <Sides
                    before={replay.totals.baseline}
                    after={replay.totals.candidate}
                    format={(side) => percent(side.pass_rate)}
                  />
                </TableCell>
                <TableCell className="num">
                  <Delta
                    value={replay.totals.delta.avg_latency_ms}
                    format={(value) => latency(value)}
                    higherIsBetter={false}
                  />
                </TableCell>
                <TableCell className="num">
                  <Delta
                    value={replay.totals.delta.total_cost_amount}
                    format={(value) => amount(value)}
                    higherIsBetter={false}
                  />
                </TableCell>
                <TableCell className="num">
                  {t('console.modelReplays.changes', {
                    regressed: replay.totals.regressed,
                    fixed: replay.totals.fixed,
                  })}
                </TableCell>
                <TableCell className="num dimmer">{relativeTime(replay.created_at)}</TableCell>
                <TableCell className="num">
                  <ConsoleButton
                    size="sm"
                    onClick={() => setOpenId(openId === replay.id ? null : replay.id)}
                  >
                    {openId === replay.id
                      ? t('console.modelReplays.hide')
                      : t('console.modelReplays.details')}
                  </ConsoleButton>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      {detail && (
        <div style={{ borderTop: '1px solid var(--border)' }} data-testid="model-replay-detail">
          <div style={{ padding: '10px 14px', fontSize: 12.5 }}>
            <b style={{ fontWeight: 600 }}>
              {t('console.modelReplays.detailTitle', { model: detail.model_ref })}
            </b>
            {detail.totals.skipped.length > 0 && (
              <span className="dimmer" style={{ marginLeft: 8 }}>
                {t('console.modelReplays.skipped', {
                  names: detail.totals.skipped.map((item) => item.agent_name).join(', '),
                })}
              </span>
            )}
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.modelReplays.subjects.agent')}</TableHead>
                <TableHead>{t('console.modelReplays.subjects.currentModel')}</TableHead>
                <TableHead>{t('console.modelReplays.columns.passRate')}</TableHead>
                <TableHead>{t('console.modelReplays.subjects.latency')}</TableHead>
                <TableHead>{t('console.modelReplays.subjects.cost')}</TableHead>
                <TableHead>{t('console.modelReplays.subjects.regressed')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {detail.subjects.map((subject) => {
                const names = new Map(subject.cases.map((item) => [item.case_id, item.name]))
                return (
                  <TableRow key={`${subject.agent_id}:${subject.dataset}`}>
                    <TableCell>
                      <b style={{ fontWeight: 600 }}>{subject.agent_name}</b>
                      <span className="mono dimmer" style={{ display: 'block', fontSize: 10.5 }}>
                        {subject.dataset} · r{subject.dataset_revision}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className="mono" style={{ fontSize: 11 }}>
                        {subject.baseline_model_ref || '—'}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Sides
                        before={subject.baseline}
                        after={subject.candidate}
                        format={(side) => `${percent(side.pass_rate)} (${side.passed}/${side.total})`}
                      />
                    </TableCell>
                    <TableCell>
                      <Sides
                        before={subject.baseline}
                        after={subject.candidate}
                        format={(side) => latency(side.avg_latency_ms)}
                      />
                    </TableCell>
                    <TableCell>
                      <Sides
                        before={subject.baseline}
                        after={subject.candidate}
                        format={(side) => amount(side.total_cost_amount)}
                      />
                    </TableCell>
                    <TableCell style={{ whiteSpace: 'normal' }}>
                      {subject.regressed.length === 0 ? (
                        <span className="dimmer">—</span>
                      ) : (
                        <span style={{ color: 'var(--danger-foreground)' }}>
                          {subject.regressed.map((id) => names.get(id) || id).join(', ')}
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      )}
      <Pager summary={t('console.modelReplays.note')} />

      <ConsoleModal
        open={creating}
        onOpenChange={(open) => !createMutation.isPending && setCreating(open)}
        title={t('console.modelReplays.createTitle')}
        note={t('console.modelReplays.createNote')}
        confirmLabel={
          createMutation.isPending ? t('console.modelReplays.running') : t('console.modelReplays.run')
        }
        confirmDisabled={!formValid}
        busy={createMutation.isPending}
        onConfirm={() => createMutation.mutate(undefined)}
      >
        <div className="mrow">
          <label>
            {t('console.modelReplays.fields.model')}
            <small>{t('console.modelReplays.fields.modelHint')}</small>
          </label>
          <input
            className="input"
            list="model-replay-options"
            value={form.modelRef}
            placeholder="model:openai:gpt-5.5"
            style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
            onChange={(event) => setForm((state) => ({ ...state, modelRef: event.target.value }))}
          />
          <datalist id="model-replay-options">
            {options.map((option) => (
              <option key={option.ref} value={option.ref}>
                {option.label}
              </option>
            ))}
          </datalist>
        </div>
        <div className="mrow">
          <label>
            {t('console.modelReplays.fields.dataset')}
            <small>{t('console.modelReplays.fields.datasetHint')}</small>
          </label>
          <input
            className="input"
            value={form.dataset}
            placeholder={t('console.modelReplays.fields.datasetAll')}
            onChange={(event) => setForm((state) => ({ ...state, dataset: event.target.value }))}
          />
        </div>
        <div className="mrow">
          <label>
            {t('console.modelReplays.fields.maxCases')}
            <small>{t('console.modelReplays.fields.maxCasesHint')}</small>
          </label>
          <input
            className="input"
            inputMode="numeric"
            value={form.maxCases}
            onChange={(event) => setForm((state) => ({ ...state, maxCases: event.target.value }))}
          />
        </div>
      </ConsoleModal>
    </WorkbenchPanel>
  )
}
