import { IdBadge } from './id-badge'
import { useTranslation } from '@/i18n'
import { API_BASE_URL } from '@/utils/request'

/** The API's origin: the configured base when it is absolute, else this page's. */
export function apiOrigin(base: string, pageOrigin: string): string {
  try {
    return new URL(base).origin
  } catch {
    return pageOrigin
  }
}

/** Where programmatic clients connect, each with a key from the table above. */
export function ClientEndpoints() {
  const { t } = useTranslation()
  const origin = apiOrigin(API_BASE_URL, typeof window === 'undefined' ? '' : window.location.origin)
  const rows = [
    { label: t('console.settings.connectPane.openai'), value: `${origin}/v1` },
    { label: t('console.settings.connectPane.mcp'), value: `${origin}/mcp` },
    { label: t('console.settings.connectPane.tools'), value: `${origin}/api/v1/tools` },
    {
      label: t('console.settings.connectPane.claudeCode'),
      value: `claude mcp add --transport http soit ${origin}/mcp --header "Authorization: Bearer $SOIT_API_KEY"`,
    },
  ]

  return (
    <div className="panel" style={{ marginTop: 14 }}>
      <div className="panel-head">
        <h2>{t('console.settings.connectPane.title')}</h2>
        <span className="hint">{t('console.settings.connectPane.hint')}</span>
      </div>
      {rows.map((row, index) => (
        // A row, not a table: on a phone the value wraps below its label and
        // clips with an ellipsis instead of running off the panel.
        <div
          key={row.label}
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            columnGap: 14,
            rowGap: 2,
            padding: '9px 14px',
            fontSize: 12.5,
            borderBottom: index < rows.length - 1 ? '1px solid var(--border)' : undefined,
          }}
        >
          <span style={{ flex: '0 0 150px', fontWeight: 500 }}>{row.label}</span>
          <span style={{ flex: '1 1 220px', minWidth: 0, display: 'flex' }}>
            <IdBadge id={row.value} maxWidth={2000} className="max-w-full" />
          </span>
        </div>
      ))}
    </div>
  )
}
