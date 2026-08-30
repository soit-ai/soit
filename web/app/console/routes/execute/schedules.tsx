import { useState } from 'react'

import { toast } from 'sonner'

import {
  ConsoleButton,
  ConsoleModal,
  ConsoleToggle,
  DataStateRow,
  IconPlus,
  Pager,
  StatusChip,
  Workbench,
  WorkbenchPanel,
  type ConsoleStatus,
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
  createSchedule,
  deleteSchedule,
  listSchedules,
  previewSchedule,
  runScheduleNow,
  updateSchedule,
  type Schedule,
} from '@/services/schedule-service'
import { requestErrorMessage } from '@/utils/request'

const EMPTY_FORM = {
  name: '',
  target_kind: 'agent',
  target_id: '',
  cron: '0 * * * *',
  timezone: 'UTC',
  input: '',
}

/** What a schedule reports about its last firing, in the shared status words. */
function outcomeOf(schedule: Schedule): { status: ConsoleStatus; label: string } {
  if (!schedule.last_status) return { status: 'na', label: 'NEVER RUN' }
  if (schedule.last_status === 'failed') return { status: 'blocked', label: 'FAILED' }
  return { status: 'pass', label: 'STARTED' }
}

export default function ConsoleSchedules() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [removing, setRemoving] = useState<Schedule | null>(null)

  const schedulesQuery = useQuery({
    queryKey: ['console', 'schedules'],
    queryFn: () => listSchedules({ limit: 200 }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const schedules = schedulesQuery.data || []

  // The next few firings for whatever is typed, so an expression can be
  // checked before it is saved rather than at two in the morning.
  const preview = useQuery({
    queryKey: ['console', 'schedules', 'preview', form.cron, form.timezone],
    queryFn: () =>
      previewSchedule(
        { cron: form.cron, timezone: form.timezone, count: 3 },
        { suppressErrorToast: true },
      ),
    options: {
      enabled: creating && form.cron.trim().length > 0,
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const onWriteError = (fallback: string) => (error: unknown) => {
    toast.error(requestErrorMessage(error, fallback))
  }

  const createMutation = useMutation<unknown, unknown, void>({
    mutationKey: ['console', 'schedules', 'create'],
    mutationFn: () =>
      createSchedule(
        {
          name: form.name.trim(),
          target_kind: form.target_kind,
          target_id: form.target_id.trim(),
          cron: form.cron.trim(),
          timezone: form.timezone.trim() || 'UTC',
          inputs: form.input.trim() ? { input: form.input.trim() } : {},
        },
        { suppressErrorToast: true },
      ),
    onSuccess: () => {
      void schedulesQuery.refetch()
      setCreating(false)
      setForm(EMPTY_FORM)
    },
    onError: onWriteError('Failed to create the schedule'),
  })

  const toggleMutation = useMutation<unknown, unknown, { id: string; enabled: boolean }>({
    mutationKey: ['console', 'schedules', 'toggle'],
    mutationFn: ({ id, enabled }) =>
      updateSchedule(id, { enabled }, { suppressErrorToast: true }),
    onSuccess: () => void schedulesQuery.refetch(),
    onError: onWriteError('Failed to change the schedule'),
  })

  const runMutation = useMutation<unknown, unknown, string>({
    mutationKey: ['console', 'schedules', 'run'],
    mutationFn: (id) => runScheduleNow(id, { suppressErrorToast: true }),
    onSuccess: () => {
      void schedulesQuery.refetch()
      toast.success(t('console.schedules.ranNow'))
    },
    onError: onWriteError('Failed to run the schedule'),
  })

  const deleteMutation = useMutation<unknown, unknown, string>({
    mutationKey: ['console', 'schedules', 'delete'],
    mutationFn: (id) => deleteSchedule(id, { suppressErrorToast: true }),
    onSuccess: () => {
      void schedulesQuery.refetch()
      setRemoving(null)
    },
    onError: onWriteError('Failed to delete the schedule'),
  })

  return (
    <Workbench
      title={t('console.schedules.title')}
      description={t('console.schedules.description')}
      actions={
        <ConsoleButton
          variant="primary"
          onClick={() => {
            setForm(EMPTY_FORM)
            setCreating(true)
          }}
        >
          <IconPlus />
          {t('console.schedules.newSchedule')}
        </ConsoleButton>
      }
    >
      <WorkbenchPanel>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('console.schedules.columns.schedule')}</TableHead>
              <TableHead>{t('console.schedules.columns.cron')}</TableHead>
              <TableHead>{t('console.schedules.columns.target')}</TableHead>
              <TableHead className="num">{t('console.schedules.columns.nextFire')}</TableHead>
              <TableHead>{t('console.schedules.columns.lastOutcome')}</TableHead>
              <TableHead>{t('console.schedules.columns.enabled')}</TableHead>
              <TableHead className="num" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {schedules.length === 0 ? (
              <DataStateRow
                colSpan={7}
                isPending={schedulesQuery.isPending}
                isError={schedulesQuery.isError}
              />
            ) : (
              schedules.map((row) => {
                const outcome = outcomeOf(row)
                return (
                  <TableRow key={row.id}>
                    <TableCell>
                      <b style={{ fontWeight: 600 }}>{row.name}</b>
                      <br />
                      <span className="dimmer" style={{ fontSize: 11 }}>
                        {row.description || row.timezone}
                      </span>
                    </TableCell>
                    <TableCell className="mono dim">{row.cron}</TableCell>
                    <TableCell>
                      <span
                        className="idm"
                        style={
                          {
                            '--c': catColor(row.target_kind),
                          } as React.CSSProperties
                        }
                      >
                        <i />
                        {row.target_id}
                      </span>
                    </TableCell>
                    <TableCell className="num dim">
                      {/* A paused schedule has no next firing, and saying
                          "paused" is more use than an em dash. */}
                      {row.enabled
                        ? row.next_fire_at
                          ? relativeTime(row.next_fire_at)
                          : '—'
                        : t('console.schedules.paused')}
                    </TableCell>
                    <TableCell>
                      {row.last_run_id ? (
                        <a
                          className="runid"
                          href={`/observe/runs/${row.last_run_id}`}
                          onClick={(event) => {
                            event.preventDefault()
                            navigate(`/observe/runs/${row.last_run_id}`)
                          }}
                        >
                          {row.last_run_id}
                        </a>
                      ) : (
                        <span className="mono dimmer">{row.last_error || ''}</span>
                      )}{' '}
                      <StatusChip status={outcome.status} label={outcome.label} />
                    </TableCell>
                    <TableCell>
                      <ConsoleToggle
                        on={row.enabled}
                        label={`${row.name} ${row.enabled ? 'enabled' : 'disabled'}`}
                        onChange={(next) =>
                          toggleMutation.mutate({ id: row.id, enabled: next })
                        }
                      />
                    </TableCell>
                    <TableCell className="num">
                      <span style={{ display: 'inline-flex', gap: 6 }}>
                        <ConsoleButton
                          variant="ghost"
                          style={{ height: 22, fontSize: 10.5 }}
                          onClick={() => runMutation.mutate(row.id)}
                          disabled={runMutation.isPending}
                        >
                          {t('console.schedules.runNow')}
                        </ConsoleButton>
                        <ConsoleButton
                          variant="ghost"
                          style={{
                            height: 22,
                            fontSize: 10.5,
                            color: 'var(--danger-foreground)',
                          }}
                          onClick={() => setRemoving(row)}
                        >
                          {t('console.common.delete')}
                        </ConsoleButton>
                      </span>
                    </TableCell>
                  </TableRow>
                )
              })
            )}
          </TableBody>
        </Table>
        <Pager summary={t('console.schedules.pagerNote')} />
      </WorkbenchPanel>

      <ConsoleModal
        open={creating}
        onOpenChange={setCreating}
        title={t('console.schedules.newTitle')}
        note={t('console.schedules.newNote')}
        confirmLabel={t('console.common.create')}
        confirmDisabled={!form.name.trim() || !form.target_id.trim() || !form.cron.trim()}
        busy={createMutation.isPending}
        onConfirm={() => createMutation.mutate(undefined)}
      >
        <div className="mrow">
          <label htmlFor="schedule-name">{t('console.schedules.fields.name')}</label>
          <input
            id="schedule-name"
            className="input"
            value={form.name}
            onChange={(event) => setForm((state) => ({ ...state, name: event.target.value }))}
          />
        </div>
        <div className="mrow">
          <label htmlFor="schedule-kind">{t('console.schedules.fields.targetKind')}</label>
          <select
            id="schedule-kind"
            className="input"
            value={form.target_kind}
            onChange={(event) =>
              setForm((state) => ({ ...state, target_kind: event.target.value }))
            }
          >
            <option value="agent">agent</option>
            <option value="workflow">workflow</option>
          </select>
        </div>
        <div className="mrow">
          <label htmlFor="schedule-target">{t('console.schedules.fields.targetId')}</label>
          <input
            id="schedule-target"
            className="input"
            value={form.target_id}
            onChange={(event) =>
              setForm((state) => ({ ...state, target_id: event.target.value }))
            }
            style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
          />
        </div>
        <div className="mrow">
          <label htmlFor="schedule-cron">
            {t('console.schedules.fields.cron')}
            <small>{t('console.schedules.fields.cronHint')}</small>
          </label>
          <input
            id="schedule-cron"
            className="input"
            value={form.cron}
            onChange={(event) => setForm((state) => ({ ...state, cron: event.target.value }))}
            style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
          />
        </div>
        <div className="mrow">
          <label htmlFor="schedule-tz">{t('console.schedules.fields.timezone')}</label>
          <input
            id="schedule-tz"
            className="input"
            value={form.timezone}
            onChange={(event) =>
              setForm((state) => ({ ...state, timezone: event.target.value }))
            }
          />
        </div>
        <div className="mrow">
          <label htmlFor="schedule-input">{t('console.schedules.fields.input')}</label>
          <input
            id="schedule-input"
            className="input"
            value={form.input}
            onChange={(event) => setForm((state) => ({ ...state, input: event.target.value }))}
          />
        </div>
        <div className="mrow">
          <label>{t('console.schedules.fields.preview')}</label>
          <div className="mono dim" style={{ fontSize: 11, display: 'grid', gap: 2 }}>
            {preview.isError ? (
              <span style={{ color: 'var(--danger-foreground)' }}>
                {t('console.schedules.previewInvalid')}
              </span>
            ) : (
              (preview.data?.fires_at || []).map((moment) => (
                <span key={moment}>{moment}</span>
              ))
            )}
          </div>
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={Boolean(removing)}
        onOpenChange={(open) => {
          if (!open) setRemoving(null)
        }}
        title={t('console.schedules.deleteTitle')}
        note={removing?.name || ''}
        confirmLabel={t('console.common.delete')}
        destructive
        busy={deleteMutation.isPending}
        onConfirm={() => removing && deleteMutation.mutate(removing.id)}
      >
        <div className="mrow">
          <span className="dim" style={{ fontSize: 12 }}>
            {t('console.schedules.deleteNote')}
          </span>
        </div>
      </ConsoleModal>
    </Workbench>
  )
}
