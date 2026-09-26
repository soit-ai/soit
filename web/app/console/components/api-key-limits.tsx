import { compactNumber } from '../adapters/palette'
import { useTranslation } from '@/i18n'
import type { ApiKeyLimits } from '@/services/api-key-service'

/** The limit fields as typed: counts and lists stay text until submitted. */
export interface ApiKeyLimitsDraft {
  ratePerMinute: string
  dailyRequests: string
  dailyTokens: string
  ipAllowlist: string
  allowedModels: string
  metadataOnly: boolean
}

export const EMPTY_LIMITS_DRAFT: ApiKeyLimitsDraft = {
  ratePerMinute: '',
  dailyRequests: '',
  dailyTokens: '',
  ipAllowlist: '',
  allowedModels: '',
  metadataOnly: false,
}

export function limitsDraftOf(key: ApiKeyLimits): ApiKeyLimitsDraft {
  return {
    ratePerMinute: key.rate_limit_per_minute ? String(key.rate_limit_per_minute) : '',
    dailyRequests: key.daily_request_quota ? String(key.daily_request_quota) : '',
    dailyTokens: key.daily_token_quota ? String(key.daily_token_quota) : '',
    ipAllowlist: (key.ip_allowlist || []).join('\n'),
    allowedModels: (key.allowed_models || []).join('\n'),
    metadataOnly: key.content_capture === 'metadata_only',
  }
}

/** A list box accepts one entry per line, or entries separated by commas. */
function listOf(text: string): string[] | null {
  const items = text
    .split(/[\s,]+/)
    .map((item) => item.trim())
    .filter(Boolean)
  return items.length ? Array.from(new Set(items)) : null
}

/** Empty means no limit; anything else must be a positive whole number. */
function countOf(text: string): number | null | 'invalid' {
  const trimmed = text.trim().replaceAll(',', '').replaceAll('_', '')
  if (!trimmed) return null
  const value = Number(trimmed)
  return Number.isSafeInteger(value) && value >= 1 ? value : 'invalid'
}

/**
 * Every limit, ready to send: an empty box sends null, which removes that
 * limit. Null while a count is not a positive whole number, so the dialog can
 * hold its confirm button rather than send something the server refuses.
 */
export function limitsPayload(draft: ApiKeyLimitsDraft): Required<ApiKeyLimits> | null {
  const rate = countOf(draft.ratePerMinute)
  const requests = countOf(draft.dailyRequests)
  const tokens = countOf(draft.dailyTokens)
  if (rate === 'invalid' || requests === 'invalid' || tokens === 'invalid') return null
  return {
    rate_limit_per_minute: rate,
    daily_request_quota: requests,
    daily_token_quota: tokens,
    ip_allowlist: listOf(draft.ipAllowlist),
    allowed_models: listOf(draft.allowedModels),
    content_capture: draft.metadataOnly ? 'metadata_only' : null,
  }
}

/** Only the limits that are set: a new key needs no nulls to be unlimited. */
export function presentLimits(limits: ApiKeyLimits | null): ApiKeyLimits {
  return Object.fromEntries(
    Object.entries(limits ?? {}).filter(([, value]) => value != null),
  ) as ApiKeyLimits
}

export function ApiKeyLimitFields({
  draft,
  onChange,
}: {
  draft: ApiKeyLimitsDraft
  onChange: (next: ApiKeyLimitsDraft) => void
}) {
  const { t } = useTranslation()
  const set = (patch: Partial<ApiKeyLimitsDraft>) => onChange({ ...draft, ...patch })
  const invalid = (text: string) => countOf(text) === 'invalid'
  const countRow = (
    field: 'ratePerMinute' | 'dailyRequests' | 'dailyTokens',
    label: string,
    hint: string,
  ) => (
    <div className="mrow">
      <label>
        {label}
        <small>{hint}</small>
      </label>
      <input
        className="input"
        inputMode="numeric"
        value={draft[field]}
        placeholder={t('console.settings.apiPane.limits.unlimited')}
        aria-invalid={invalid(draft[field]) || undefined}
        style={invalid(draft[field]) ? { borderColor: 'var(--danger-foreground)' } : undefined}
        onChange={(event) => onChange({ ...draft, [field]: event.target.value })}
      />
    </div>
  )

  return (
    <>
      {countRow(
        'ratePerMinute',
        t('console.settings.apiPane.limits.rate'),
        t('console.settings.apiPane.limits.rateHint'),
      )}
      {countRow(
        'dailyRequests',
        t('console.settings.apiPane.limits.dailyRequests'),
        t('console.settings.apiPane.limits.dailyRequestsHint'),
      )}
      {countRow(
        'dailyTokens',
        t('console.settings.apiPane.limits.dailyTokens'),
        t('console.settings.apiPane.limits.dailyTokensHint'),
      )}
      <div className="mrow">
        <label>
          {t('console.settings.apiPane.limits.ipAllowlist')}
          <small>{t('console.settings.apiPane.limits.ipAllowlistHint')}</small>
        </label>
        <textarea
          className="input"
          value={draft.ipAllowlist}
          placeholder={'203.0.113.7\n198.51.100.0/24'}
          onChange={(event) => set({ ipAllowlist: event.target.value })}
        />
      </div>
      <div className="mrow">
        <label>
          {t('console.settings.apiPane.limits.allowedModels')}
          <small>{t('console.settings.apiPane.limits.allowedModelsHint')}</small>
        </label>
        <textarea
          className="input"
          value={draft.allowedModels}
          placeholder={'model:openai:gpt-5.5\nvmodel:support'}
          onChange={(event) => set({ allowedModels: event.target.value })}
        />
      </div>
      <div className="mrow">
        <label>
          {t('console.settings.apiPane.limits.content')}
          <small>{t('console.settings.apiPane.limits.contentHint')}</small>
        </label>
        <select
          className="input"
          value={draft.metadataOnly ? 'metadata_only' : 'workspace'}
          onChange={(event) => set({ metadataOnly: event.target.value === 'metadata_only' })}
        >
          <option value="workspace">{t('console.settings.apiPane.limits.contentWorkspace')}</option>
          <option value="metadata_only">
            {t('console.settings.apiPane.limits.contentMetadataOnly')}
          </option>
        </select>
      </div>
    </>
  )
}

/** One line for the key table: what bounds the key, or a dash. */
export function ApiKeyLimitsSummary({ limits }: { limits: ApiKeyLimits }) {
  const { t } = useTranslation()
  const parts: string[] = []
  if (limits.rate_limit_per_minute) {
    parts.push(
      t('console.settings.apiPane.limits.perMinute', {
        value: compactNumber(limits.rate_limit_per_minute),
      }),
    )
  }
  if (limits.daily_request_quota) {
    parts.push(
      t('console.settings.apiPane.limits.callsPerDay', {
        value: compactNumber(limits.daily_request_quota),
      }),
    )
  }
  if (limits.daily_token_quota) {
    parts.push(
      t('console.settings.apiPane.limits.tokensPerDay', {
        value: compactNumber(limits.daily_token_quota),
      }),
    )
  }
  if (limits.ip_allowlist?.length) {
    parts.push(t('console.settings.apiPane.limits.addresses', { count: limits.ip_allowlist.length }))
  }
  if (limits.allowed_models?.length) {
    parts.push(t('console.settings.apiPane.limits.models', { count: limits.allowed_models.length }))
  }
  if (limits.content_capture === 'metadata_only') {
    parts.push(t('console.settings.apiPane.limits.noContent'))
  }
  if (!parts.length) return <span className="dimmer">—</span>
  return <span className="mono dim" style={{ fontSize: 11 }}>{parts.join(' · ')}</span>
}
