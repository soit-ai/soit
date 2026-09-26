import { useState } from 'react'

import { toast } from 'sonner'

import { ConsoleButton } from './button'
import { DataStateRow } from './data-state'
import { IconPlus } from './icons'
import { ConsoleModal } from './modal'
import { Pager } from './pager'
import { StatusChip } from './status-chip'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui'
import { WorkbenchPanel } from './workbench'
import { relativeTime } from '../adapters/palette'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import {
  MAX_VIRTUAL_MODEL_TARGETS,
  createVirtualModel,
  deleteVirtualModel,
  listVirtualModels,
  updateVirtualModel,
  type VirtualModel,
} from '@/services/provider-service'
import { requestErrorMessage } from '@/utils/request'

/** A concrete model a virtual model can route to. */
export interface VirtualModelTargetOption {
  ref: string
  label: string
}

const SLUG_PATTERN = /^[a-z0-9][a-z0-9._-]{0,62}$/

interface VirtualModelForm {
  slug: string
  name: string
  description: string
  targets: string[]
  /** The ref typed or picked, waiting to be added. */
  pending: string
}

const EMPTY_FORM: VirtualModelForm = {
  slug: '',
  name: '',
  description: '',
  targets: [],
  pending: '',
}

/**
 * Build › Models › Virtual models: workspace names for an ordered failover
 * list of model refs. Targets are picked from the model library or typed as a
 * `model:` ref, and reordered, because order is the failover order.
 */
export function VirtualModelsPanel({ options }: { options: VirtualModelTargetOption[] }) {
  const { t } = useTranslation()
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<VirtualModel | null>(null)
  const [deleting, setDeleting] = useState<VirtualModel | null>(null)
  const [form, setForm] = useState<VirtualModelForm>(EMPTY_FORM)

  const virtualModelsQuery = useQuery({
    queryKey: ['console', 'models', 'virtual'],
    queryFn: () => listVirtualModels({ suppressErrorToast: true }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const virtualModels = virtualModelsQuery.data || []

  const afterWrite = () => {
    void virtualModelsQuery.refetch()
    setCreating(false)
    setEditing(null)
    setDeleting(null)
    setForm(EMPTY_FORM)
  }
  const onWriteError = (fallback: string) => (error: unknown) => {
    toast.error(requestErrorMessage(error, fallback))
  }

  const createMutation = useMutation({
    mutationKey: ['console', 'models', 'virtual', 'create'],
    mutationFn: () =>
      createVirtualModel(
        {
          slug: form.slug.trim(),
          name: form.name.trim(),
          ...(form.description.trim() ? { description: form.description.trim() } : {}),
          targets: form.targets,
        },
        { suppressErrorToast: true },
      ),
    onSuccess: afterWrite,
    onError: onWriteError('Failed to create the virtual model'),
  })
  const updateMutation = useMutation({
    mutationKey: ['console', 'models', 'virtual', 'update'],
    mutationFn: () =>
      updateVirtualModel(
        editing!.id,
        {
          name: form.name.trim(),
          description: form.description.trim() || null,
          targets: form.targets,
        },
        { suppressErrorToast: true },
      ),
    onSuccess: afterWrite,
    onError: onWriteError('Failed to change the virtual model'),
  })
  const toggleMutation = useMutation<unknown, unknown, VirtualModel>({
    mutationKey: ['console', 'models', 'virtual', 'toggle'],
    mutationFn: (model: VirtualModel) =>
      updateVirtualModel(
        model.id,
        { status: model.status === 'active' ? 'disabled' : 'active' },
        { suppressErrorToast: true },
      ),
    onSuccess: () => {
      void virtualModelsQuery.refetch()
    },
    onError: onWriteError('Failed to change the virtual model'),
  })
  const deleteMutation = useMutation({
    mutationKey: ['console', 'models', 'virtual', 'delete'],
    mutationFn: () => deleteVirtualModel(deleting!.id, { suppressErrorToast: true }),
    onSuccess: afterWrite,
    onError: onWriteError('Failed to delete the virtual model'),
  })

  const labelOf = (ref: string) => options.find((option) => option.ref === ref)?.label
  const pending = form.pending.trim()
  const canAdd =
    pending.startsWith('model:') &&
    !form.targets.includes(pending) &&
    form.targets.length < MAX_VIRTUAL_MODEL_TARGETS
  const addPending = () => {
    if (!canAdd) return
    setForm((state) => ({ ...state, targets: [...state.targets, pending], pending: '' }))
  }
  const move = (index: number, offset: -1 | 1) =>
    setForm((state) => {
      const targets = [...state.targets]
      const [item] = targets.splice(index, 1)
      targets.splice(index + offset, 0, item)
      return { ...state, targets }
    })
  const remove = (index: number) =>
    setForm((state) => ({ ...state, targets: state.targets.filter((_, at) => at !== index) }))

  const formValid =
    Boolean(form.name.trim()) &&
    form.targets.length > 0 &&
    (editing != null || SLUG_PATTERN.test(form.slug.trim()))

  const formRows = (
    <>
      <div className="mrow">
        <label>
          {t('console.virtualModels.fields.slug')}
          <small>{t('console.virtualModels.fields.slugHint')}</small>
        </label>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className="mono dim">vmodel:</span>
          <input
            className="input"
            value={form.slug}
            disabled={editing != null}
            placeholder="support-chat"
            style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
            onChange={(event) =>
              setForm((state) => ({ ...state, slug: event.target.value.toLowerCase() }))
            }
          />
        </div>
      </div>
      <div className="mrow">
        <label>{t('console.virtualModels.fields.name')}</label>
        <input
          className="input"
          value={form.name}
          onChange={(event) => setForm((state) => ({ ...state, name: event.target.value }))}
        />
      </div>
      <div className="mrow">
        <label>{t('console.virtualModels.fields.description')}</label>
        <input
          className="input"
          value={form.description}
          onChange={(event) => setForm((state) => ({ ...state, description: event.target.value }))}
        />
      </div>
      <div className="mrow">
        <label>
          {t('console.virtualModels.fields.targets')}
          <small>
            {t('console.virtualModels.fields.targetsHint', { max: MAX_VIRTUAL_MODEL_TARGETS })}
          </small>
        </label>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <ol style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {form.targets.map((ref, index) => (
              <li
                key={ref}
                data-testid="virtual-model-target"
                style={{ display: 'flex', alignItems: 'center', gap: 6 }}
              >
                <span className="mono dimmer" style={{ width: 16 }}>
                  {index + 1}
                </span>
                <span className="mono" style={{ fontSize: 11.5, flex: 1, minWidth: 0 }}>
                  {ref}
                  {labelOf(ref) && (
                    <span className="dimmer" style={{ marginLeft: 6 }}>
                      {labelOf(ref)}
                    </span>
                  )}
                </span>
                <ConsoleButton
                  variant="ghost"
                  size="sm"
                  aria-label={t('console.virtualModels.moveUp')}
                  disabled={index === 0}
                  onClick={() => move(index, -1)}
                >
                  ↑
                </ConsoleButton>
                <ConsoleButton
                  variant="ghost"
                  size="sm"
                  aria-label={t('console.virtualModels.moveDown')}
                  disabled={index === form.targets.length - 1}
                  onClick={() => move(index, 1)}
                >
                  ↓
                </ConsoleButton>
                <ConsoleButton
                  variant="ghost"
                  size="sm"
                  aria-label={t('console.virtualModels.removeTarget')}
                  onClick={() => remove(index)}
                >
                  ×
                </ConsoleButton>
              </li>
            ))}
          </ol>
          <div style={{ display: 'flex', gap: 6 }}>
            <input
              className="input"
              list="virtual-model-target-options"
              aria-label={t('console.virtualModels.fields.addTarget')}
              value={form.pending}
              placeholder="model:openai:gpt-5.5"
              style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
              onChange={(event) => setForm((state) => ({ ...state, pending: event.target.value }))}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault()
                  addPending()
                }
              }}
            />
            <datalist id="virtual-model-target-options">
              {options
                .filter((option) => !form.targets.includes(option.ref))
                .map((option) => (
                  <option key={option.ref} value={option.ref}>
                    {option.label}
                  </option>
                ))}
            </datalist>
            <ConsoleButton disabled={!canAdd} onClick={addPending}>
              {t('console.virtualModels.add')}
            </ConsoleButton>
          </div>
        </div>
      </div>
    </>
  )

  return (
    <WorkbenchPanel
      className="mt-3.5"
      title={t('console.virtualModels.title')}
      hint={t('console.virtualModels.hint')}
      actions={
        <ConsoleButton
          variant="primary"
          size="sm"
          onClick={() => {
            setForm(EMPTY_FORM)
            setCreating(true)
          }}
        >
          <IconPlus />
          {t('console.virtualModels.create')}
        </ConsoleButton>
      }
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t('console.virtualModels.columns.name')}</TableHead>
            <TableHead>{t('console.virtualModels.columns.targets')}</TableHead>
            <TableHead className="num">{t('console.virtualModels.columns.status')}</TableHead>
            <TableHead className="num">{t('console.virtualModels.columns.updated')}</TableHead>
            <TableHead className="num" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {virtualModels.length === 0 ? (
            <DataStateRow
              colSpan={5}
              isPending={virtualModelsQuery.isPending}
              isError={virtualModelsQuery.isError}
              emptyLabel={t('console.virtualModels.empty')}
            />
          ) : (
            virtualModels.map((model) => (
              <TableRow key={model.id}>
                <TableCell>
                  <b style={{ fontWeight: 600 }}>{model.name}</b>
                  <span className="mono dimmer" style={{ display: 'block', fontSize: 10.5 }}>
                    {model.model_ref}
                  </span>
                </TableCell>
                <TableCell>
                  <span className="mono" style={{ fontSize: 11 }}>
                    {model.targets.join(' → ')}
                  </span>
                </TableCell>
                <TableCell className="num">
                  <StatusChip status={model.status === 'active' ? 'enabled' : 'disabled'} />
                </TableCell>
                <TableCell className="num dimmer">{relativeTime(model.updated_at)}</TableCell>
                <TableCell className="num">
                  <span style={{ display: 'inline-flex', gap: 6 }}>
                    <ConsoleButton
                      size="sm"
                      onClick={() => {
                        setForm({
                          slug: model.slug,
                          name: model.name,
                          description: model.description || '',
                          targets: [...model.targets],
                          pending: '',
                        })
                        setEditing(model)
                      }}
                    >
                      {t('console.virtualModels.edit')}
                    </ConsoleButton>
                    <ConsoleButton
                      variant="ghost"
                      size="sm"
                      disabled={toggleMutation.isPending}
                      onClick={() => toggleMutation.mutate(model)}
                    >
                      {model.status === 'active'
                        ? t('console.virtualModels.disable')
                        : t('console.virtualModels.enable')}
                    </ConsoleButton>
                    <ConsoleButton
                      variant="ghost"
                      size="sm"
                      style={{ color: 'var(--danger-foreground)' }}
                      onClick={() => setDeleting(model)}
                    >
                      {t('console.virtualModels.delete')}
                    </ConsoleButton>
                  </span>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
      <Pager summary={t('console.virtualModels.note')} />

      <ConsoleModal
        open={creating}
        onOpenChange={setCreating}
        title={t('console.virtualModels.createTitle')}
        note={t('console.virtualModels.createNote')}
        confirmLabel={t('console.common.create')}
        confirmDisabled={!formValid}
        busy={createMutation.isPending}
        onConfirm={() => createMutation.mutate(undefined)}
      >
        {formRows}
      </ConsoleModal>

      <ConsoleModal
        open={editing != null}
        onOpenChange={(open) => !open && setEditing(null)}
        title={t('console.virtualModels.editTitle')}
        note={t('console.virtualModels.editNote')}
        confirmLabel={t('console.common.save')}
        confirmDisabled={!formValid}
        busy={updateMutation.isPending}
        onConfirm={() => updateMutation.mutate(undefined)}
      >
        {formRows}
      </ConsoleModal>

      <ConsoleModal
        open={deleting != null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={t('console.virtualModels.deleteTitle')}
        confirmLabel={t('console.virtualModels.delete')}
        destructive
        busy={deleteMutation.isPending}
        onConfirm={() => deleteMutation.mutate(undefined)}
      >
        <div style={{ padding: '12px 16px', fontSize: 12.5, lineHeight: 1.6 }} className="dim">
          {t('console.virtualModels.deleteConfirm', { ref: deleting?.model_ref ?? '' })}
        </div>
      </ConsoleModal>
    </WorkbenchPanel>
  )
}
