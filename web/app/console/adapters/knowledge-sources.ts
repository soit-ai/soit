/**
 * Knowledge source form logic: turning a connector descriptor into form
 * values and back, schedule presets and run-status presentation.
 *
 * Kept free of React so the conversions are testable on their own. The server
 * validates everything again; this only has to produce a request it can read
 * and to say what is missing before one is sent.
 */

import type { ConsoleStatus } from '../components'
import type {
  ConnectorField,
  KnowledgeConnector,
  KnowledgeSourceCounts,
  KnowledgeSyncRun,
} from '@/services/knowledge-service'

/** Form state for one setting: text for inputs, a boolean for a checkbox. */
export type FieldValue = string | boolean
export type FieldValues = Record<string, FieldValue>

const MB = 1024 * 1024

export interface SchedulePreset {
  key: string
  /** Cron expression; empty for manual-only. */
  cron: string
  labelKey:
    | 'console.knowDetail.sources.schedule.manual'
    | 'console.knowDetail.sources.schedule.hourly'
    | 'console.knowDetail.sources.schedule.sixHourly'
    | 'console.knowDetail.sources.schedule.daily'
    | 'console.knowDetail.sources.schedule.weekly'
}

export const SCHEDULE_PRESETS: SchedulePreset[] = [
  { key: 'manual', cron: '', labelKey: 'console.knowDetail.sources.schedule.manual' },
  { key: 'hourly', cron: '0 * * * *', labelKey: 'console.knowDetail.sources.schedule.hourly' },
  { key: 'six-hourly', cron: '0 */6 * * *', labelKey: 'console.knowDetail.sources.schedule.sixHourly' },
  { key: 'daily', cron: '0 2 * * *', labelKey: 'console.knowDetail.sources.schedule.daily' },
  { key: 'weekly', cron: '0 2 * * 1', labelKey: 'console.knowDetail.sources.schedule.weekly' },
]

export const CUSTOM_SCHEDULE = 'custom'

/** The preset key a stored cron expression matches, or `custom`. */
export function schedulePresetOf(cron: string | null | undefined): string {
  const expression = (cron ?? '').trim().replace(/\s+/g, ' ')
  const match = SCHEDULE_PRESETS.find((preset) => preset.cron === expression)
  return match ? match.key : CUSTOM_SCHEDULE
}

/** The cron expression a preset stands for; `custom` keeps what was typed. */
export function cronForPreset(key: string, custom: string): string {
  if (key === CUSTOM_SCHEDULE) return custom.trim().replace(/\s+/g, ' ')
  return SCHEDULE_PRESETS.find((preset) => preset.key === key)?.cron ?? ''
}

/** Starting values for a new source of a kind: each field's default, else empty. */
export function defaultFieldValues(connector: KnowledgeConnector | undefined): FieldValues {
  const values: FieldValues = {}
  for (const field of connector?.fields ?? []) {
    values[field.key] = initialValue(field, field.default)
  }
  return values
}

function initialValue(field: ConnectorField, value: unknown): FieldValue {
  switch (field.type) {
    case 'boolean':
      return value === true
    case 'string_list':
      return Array.isArray(value) ? value.map(String).join('\n') : ''
    case 'integer':
      return typeof value === 'number' ? String(value) : ''
    default:
      return typeof value === 'string' ? value : ''
  }
}

/** Form values for a saved source's stored configuration. */
export function fieldValuesFromConfig(
  connector: KnowledgeConnector | undefined,
  config: Record<string, unknown>,
): FieldValues {
  const values: FieldValues = {}
  for (const field of connector?.fields ?? []) {
    values[field.key] = initialValue(field, config[field.key] ?? field.default)
  }
  return values
}

/**
 * The configuration to send: values typed as each field declares, and anything
 * left empty omitted so the server's own default applies.
 */
export function configFromFieldValues(
  connector: KnowledgeConnector | undefined,
  values: FieldValues,
): Record<string, unknown> {
  const config: Record<string, unknown> = {}
  for (const field of connector?.fields ?? []) {
    const raw = values[field.key]
    switch (field.type) {
      case 'boolean':
        // An unchecked box that was never touched stays unset, so a connector
        // whose default depends on other settings can still apply it.
        if (raw === true || (raw === false && field.default === true)) config[field.key] = raw
        break
      case 'string_list': {
        const lines = String(raw ?? '')
          .split('\n')
          .map((line) => line.trim())
          .filter(Boolean)
        if (lines.length) config[field.key] = lines
        break
      }
      case 'integer': {
        const text = String(raw ?? '').trim()
        if (text !== '' && Number.isFinite(Number(text))) config[field.key] = Number(text)
        break
      }
      default: {
        const text = String(raw ?? '').trim()
        if (text) config[field.key] = text
      }
    }
  }
  return config
}

/** Labels of the required fields that have no value yet. */
export function missingRequiredFields(
  connector: KnowledgeConnector | undefined,
  values: FieldValues,
): string[] {
  const config = configFromFieldValues(connector, values)
  return (connector?.fields ?? [])
    .filter((field) => field.required && config[field.key] === undefined)
    .map((field) => field.label)
}

export interface LimitInputs {
  maxItems: string
  maxItemMb: string
  maxTotalMb: string
}

/**
 * The limits request body; an empty box leaves that cap at the deployment
 * default. With a `baseline` (the boxes as the form opened) only the caps that
 * were changed are sent, so saving a source never pins the defaults it showed.
 */
export function limitsFromInputs(
  inputs: LimitInputs,
  baseline?: LimitInputs,
): { max_items?: number; max_item_bytes?: number; max_total_bytes?: number } | null {
  const limits: { max_items?: number; max_item_bytes?: number; max_total_bytes?: number } = {}
  const changed = (key: keyof LimitInputs) => !baseline || baseline[key].trim() !== inputs[key].trim()
  const items = Number(inputs.maxItems)
  if (changed('maxItems') && inputs.maxItems.trim() !== '' && Number.isFinite(items) && items > 0) {
    limits.max_items = Math.floor(items)
  }
  const itemMb = Number(inputs.maxItemMb)
  if (changed('maxItemMb') && inputs.maxItemMb.trim() !== '' && Number.isFinite(itemMb) && itemMb > 0) {
    limits.max_item_bytes = Math.floor(itemMb * MB)
  }
  const totalMb = Number(inputs.maxTotalMb)
  if (changed('maxTotalMb') && inputs.maxTotalMb.trim() !== '' && Number.isFinite(totalMb) && totalMb > 0) {
    limits.max_total_bytes = Math.floor(totalMb * MB)
  }
  return Object.keys(limits).length ? limits : null
}

/** A byte count as megabytes for an input box (whole numbers when they are). */
export function bytesToMb(bytes: number | null | undefined): string {
  if (!bytes) return ''
  const mb = bytes / MB
  return Number.isInteger(mb) ? String(mb) : mb.toFixed(2).replace(/0+$/, '').replace(/\.$/, '')
}

/** Sync run status → shared console status vocabulary. */
export function syncRunStatus(status: string | null | undefined): ConsoleStatus {
  switch (status) {
    case 'succeeded':
      return 'succeeded'
    case 'partial':
      return 'degraded'
    case 'failed':
      return 'failed'
    case 'running':
      return 'running'
    case 'queued':
      return 'queued'
    case 'canceled':
      return 'cancelled'
    default:
      return 'info'
  }
}

/** Whether a run is still queued or running, so it can be cancelled. */
export function isActiveRun(run: Pick<KnowledgeSyncRun, 'status'>): boolean {
  return run.status === 'queued' || run.status === 'running'
}

/** A compact tally such as `+3 ~1 -2 !1`, leaving out what is zero. */
export function countsSummary(counts: KnowledgeSourceCounts | undefined): string {
  if (!counts) return ''
  const parts: string[] = []
  if (counts.added) parts.push(`+${counts.added}`)
  if (counts.updated) parts.push(`~${counts.updated}`)
  if (counts.removed) parts.push(`-${counts.removed}`)
  if (counts.failed) parts.push(`!${counts.failed}`)
  return parts.join(' ')
}

/** How long a finished run took, such as `42s` or `3m 05s`. */
export function runDuration(run: Pick<KnowledgeSyncRun, 'started_at' | 'finished_at'>): string {
  if (!run.started_at || !run.finished_at) return '—'
  const seconds = Math.max(
    0,
    Math.round((new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000),
  )
  if (Number.isNaN(seconds)) return '—'
  if (seconds < 60) return `${seconds}s`
  return `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, '0')}s`
}

/** How far off a future moment is, such as `in 3h`; a past or missing one reads as `—`. */
export function relativeFuture(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return '—'
  const at = new Date(iso).getTime()
  if (Number.isNaN(at)) return '—'
  const minutes = Math.round((at - now) / 60_000)
  if (minutes < 1) return 'due'
  if (minutes < 60) return `in ${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `in ${hours}h`
  return `in ${Math.floor(hours / 24)}d`
}
