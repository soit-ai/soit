import { ConsoleButton } from '../../components'
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import { useTranslation } from '@/i18n'

/** Secrets are governed elsewhere; this pane points there. */
export function SecretsPane() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>{t('console.settings.secrets')}</h2>
      </div>
      <div style={{ padding: '18px 14px' }}>
        <p className="dim" style={{ fontSize: 12.5, maxWidth: 520, lineHeight: 1.6 }}>
          {t('console.settings.secretsPane.body')}
        </p>
        <ConsoleButton
          variant="primary"
          style={{ marginTop: 12 }}
          onClick={() => navigate('/govern/secrets')}
        >
          {t('console.settings.secretsPane.open')}
        </ConsoleButton>
      </div>
    </div>
  )
}
