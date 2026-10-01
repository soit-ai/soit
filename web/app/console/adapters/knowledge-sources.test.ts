import { describe, expect, it } from 'vitest'

import type { KnowledgeConnector } from '@/services/knowledge-service'

import {
  bytesToMb,
  configFromFieldValues,
  countsSummary,
  cronForPreset,
  defaultFieldValues,
  fieldValuesFromConfig,
  isActiveRun,
  limitsFromInputs,
  missingRequiredFields,
  relativeFuture,
  runDuration,
  schedulePresetOf,
  syncRunStatus,
} from './knowledge-sources'

const connector: KnowledgeConnector = {
  kind: 's3',
  label: 'S3-compatible storage',
  description: '',
  secret: 'required',
  fields: [
    { key: 'bucket', label: 'Bucket', type: 'string', required: true, options: [] },
    { key: 'region', label: 'Region', type: 'string', required: false, default: 'us-east-1', options: [] },
    { key: 'include', label: 'Include patterns', type: 'string_list', required: false, options: [] },
    { key: 'max_depth', label: 'Max depth', type: 'integer', required: false, default: 2, options: [] },
    { key: 'path_style', label: 'Path-style', type: 'boolean', required: false, options: [] },
    { key: 'verify', label: 'Verify', type: 'boolean', required: false, default: true, options: [] },
  ],
}

describe('schedule presets', () => {
  it('recognises preset expressions however they are spaced', () => {
    expect(schedulePresetOf('0 2 * * *')).toBe('daily')
    expect(schedulePresetOf('  0   2 * * * ')).toBe('daily')
    expect(schedulePresetOf('')).toBe('manual')
    expect(schedulePresetOf(null)).toBe('manual')
    expect(schedulePresetOf('*/20 * * * *')).toBe('custom')
  })

  it('maps a preset back to its cron and keeps a custom one as typed', () => {
    expect(cronForPreset('hourly', 'ignored')).toBe('0 * * * *')
    expect(cronForPreset('manual', 'ignored')).toBe('')
    expect(cronForPreset('custom', ' */20   * * * * ')).toBe('*/20 * * * *')
  })
})

describe('connector form values', () => {
  it('starts from each field default', () => {
    expect(defaultFieldValues(connector)).toEqual({
      bucket: '',
      region: 'us-east-1',
      include: '',
      max_depth: '2',
      path_style: false,
      verify: true,
    })
  })

  it('builds a typed config and leaves empty fields out', () => {
    const config = configFromFieldValues(connector, {
      bucket: ' docs ',
      region: '',
      include: '*.pdf\n\n  docs/*  \n',
      max_depth: '3',
      path_style: true,
      verify: true,
    })

    expect(config).toEqual({
      bucket: 'docs',
      include: ['*.pdf', 'docs/*'],
      max_depth: 3,
      path_style: true,
      verify: true,
    })
  })

  it('keeps an unchecked box unset unless its default was on', () => {
    const config = configFromFieldValues(connector, { bucket: 'b', path_style: false, verify: false })

    expect(config.path_style).toBeUndefined()
    expect(config.verify).toBe(false)
  })

  it('reads a stored config back into form values', () => {
    const values = fieldValuesFromConfig(connector, {
      bucket: 'docs',
      include: ['*.pdf', 'docs/*'],
      max_depth: 4,
      path_style: true,
    })

    expect(values).toMatchObject({
      bucket: 'docs',
      region: 'us-east-1',
      include: '*.pdf\ndocs/*',
      max_depth: '4',
      path_style: true,
    })
  })

  it('names the required fields still empty', () => {
    expect(missingRequiredFields(connector, defaultFieldValues(connector))).toEqual(['Bucket'])
    expect(missingRequiredFields(connector, { ...defaultFieldValues(connector), bucket: 'docs' })).toEqual([])
    expect(missingRequiredFields(undefined, {})).toEqual([])
  })
})

describe('limits', () => {
  it('sends only the caps that were filled in, in bytes', () => {
    expect(limitsFromInputs({ maxItems: '', maxItemMb: '', maxTotalMb: '' })).toBeNull()
    expect(limitsFromInputs({ maxItems: '500', maxItemMb: '2', maxTotalMb: '0.5' })).toEqual({
      max_items: 500,
      max_item_bytes: 2 * 1024 * 1024,
      max_total_bytes: 512 * 1024,
    })
    expect(limitsFromInputs({ maxItems: '-3', maxItemMb: 'abc', maxTotalMb: '0' })).toBeNull()
  })

  it('sends only the caps changed from the values the form opened with', () => {
    const baseline = { maxItems: '1000', maxItemMb: '5', maxTotalMb: '256' }

    expect(limitsFromInputs(baseline, baseline)).toBeNull()
    expect(limitsFromInputs({ ...baseline, maxItemMb: '10' }, baseline)).toEqual({
      max_item_bytes: 10 * 1024 * 1024,
    })
  })

  it('shows bytes as tidy megabytes', () => {
    expect(bytesToMb(5 * 1024 * 1024)).toBe('5')
    expect(bytesToMb(512 * 1024)).toBe('0.5')
    expect(bytesToMb(0)).toBe('')
    expect(bytesToMb(null)).toBe('')
  })
})

describe('run presentation', () => {
  it('maps sync statuses onto the console vocabulary', () => {
    expect(syncRunStatus('succeeded')).toBe('succeeded')
    expect(syncRunStatus('partial')).toBe('degraded')
    expect(syncRunStatus('canceled')).toBe('cancelled')
    expect(syncRunStatus('queued')).toBe('queued')
    expect(syncRunStatus('failed')).toBe('failed')
    expect(syncRunStatus(null)).toBe('info')
  })

  it('knows which runs can still be cancelled', () => {
    expect(isActiveRun({ status: 'queued' })).toBe(true)
    expect(isActiveRun({ status: 'running' })).toBe(true)
    expect(isActiveRun({ status: 'failed' })).toBe(false)
  })

  it('summarises counts and drops the zeros', () => {
    expect(countsSummary({ added: 3, updated: 0, removed: 2, failed: 1 })).toBe('+3 -2 !1')
    expect(countsSummary({ unchanged: 40 })).toBe('')
    expect(countsSummary(undefined)).toBe('')
  })

  it('formats how long a run took', () => {
    expect(runDuration({ started_at: '2026-10-01T10:00:00Z', finished_at: '2026-10-01T10:00:42Z' })).toBe('42s')
    expect(runDuration({ started_at: '2026-10-01T10:00:00Z', finished_at: '2026-10-01T10:03:05Z' })).toBe('3m 05s')
    expect(runDuration({ started_at: '2026-10-01T10:00:00Z', finished_at: null })).toBe('—')
  })
})

describe('relativeFuture', () => {
  const now = new Date('2026-10-01T10:00:00Z').getTime()

  it('reads how far off a moment is', () => {
    expect(relativeFuture('2026-10-01T10:20:00Z', now)).toBe('in 20m')
    expect(relativeFuture('2026-10-01T13:10:00Z', now)).toBe('in 3h')
    expect(relativeFuture('2026-10-04T10:00:00Z', now)).toBe('in 3d')
  })

  it('says due for the past and a dash for nothing', () => {
    expect(relativeFuture('2026-10-01T09:00:00Z', now)).toBe('due')
    expect(relativeFuture(null, now)).toBe('—')
    expect(relativeFuture('not a date', now)).toBe('—')
  })
})
