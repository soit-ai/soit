import { KeyValueList } from '../../components'
import { useDiagnosticsQuery } from './shared'
import { useTranslation } from '@/i18n'
import type { TFunction } from '@/i18n/types'
import type { EditionDiagnostic } from '@/services/diagnostics-service'

/**
 * The edition the runtime resolved from its license file. A license that is
 * configured but grants nothing (expired, unverifiable) says why, since the
 * deployment has quietly dropped to Community.
 */
function editionLabel(edition: EditionDiagnostic | undefined, t: TFunction): string {
  if (!edition) return '—'
  if (edition.license_status === 'active') {
    return t('console.settings.aboutPane.editionLicensed', {
      edition: edition.edition.charAt(0).toUpperCase() + edition.edition.slice(1),
      license: edition.license_id,
      customer: edition.customer_id,
      days: edition.days_left ?? 0,
    })
  }
  if (edition.license_status === 'absent') return t('console.settings.aboutPane.editionCommunity')
  return t('console.settings.aboutPane.editionUnlicensed', { reason: edition.reason ?? edition.license_status })
}

export function AboutPane() {
  const { t } = useTranslation()
  const diagnostics = useDiagnosticsQuery(true).data

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>{t('console.settings.about')}</h2>
      </div>
      <KeyValueList
        items={[
          // Stamped from package.json at build time by Vite.
          { key: t('console.settings.aboutPane.console'), value: `soit-web ${__CONSOLE_VERSION__}` },
          {
            key: t('console.settings.aboutPane.runtime'),
            value: diagnostics ? `soit-server ${diagnostics.version} · ${diagnostics.environment}` : '—',
          },
          { key: t('console.settings.aboutPane.edition'), value: editionLabel(diagnostics?.edition, t) },
          // Project fact, not workspace data.
          { key: t('console.settings.aboutPane.license'), value: 'Apache 2.0 · open source' },
          {
            key: t('console.settings.aboutPane.repository'),
            value: (
              <a
                className="runid"
                href="https://github.com/soit-ai/soit"
                target="_blank"
                rel="noopener noreferrer"
              >
                github.com/soit-ai/soit
              </a>
            ),
          },
        ]}
      />
      <div className="code">
        <span className="k">$</span> soit diagnostics export
        {'\n'}
        <span className="s">{t('console.settings.aboutPane.diagNote')}</span>
      </div>
    </div>
  )
}
