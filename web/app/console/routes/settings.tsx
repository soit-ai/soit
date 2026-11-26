import { Navigate, useLocation, useParams } from 'react-router'

import { AboutPane } from './settings/about-pane'
import { AccountPane } from './settings/account-pane'
import { ApiPane } from './settings/api-pane'
import { AppearancePane } from './settings/appearance-pane'
import { BillingPane } from './settings/billing-pane'
import { NotificationsPane } from './settings/notifications-pane'
import { SecretsPane } from './settings/secrets-pane'
import { SecurityPane } from './settings/security-pane'
import { TeamPane } from './settings/team-pane'
import { useTranslation } from '@/i18n'

type SettingsSection =
  | 'account'
  | 'team'
  | 'api'
  | 'security'
  | 'secrets'
  | 'notifications'
  | 'appearance'
  | 'billing'
  | 'about'

const SECTIONS: SettingsSection[] = [
  'account',
  'team',
  'api',
  'security',
  'secrets',
  'notifications',
  'appearance',
  'billing',
  'about',
]

/**
 * The settings route. Each section is a pane of its own that owns its
 * queries, writes and dialogs, so only the chosen section's requests run.
 */
export default function ConsoleSettings() {
  const { t } = useTranslation()
  const { section } = useParams<{ section?: string }>()
  const location = useLocation()

  const active = ((SECTIONS as string[]).includes(section || '')
    ? section
    : 'account') as SettingsSection

  if (!section) {
    return <Navigate to={`/settings/account${location.search}`} replace />
  }

  return (
    <>
      <div className="page-head">
        <h1>{t('console.settings.title')}</h1>
        <p>{t('console.settings.description')}</p>
      </div>
      <div style={{ maxWidth: 860 }}>
        {active === 'account' && <AccountPane />}
        {active === 'team' && <TeamPane />}
        {active === 'api' && <ApiPane />}
        {active === 'security' && <SecurityPane />}
        {active === 'secrets' && <SecretsPane />}
        {active === 'notifications' && <NotificationsPane />}
        {active === 'billing' && <BillingPane />}
        {/* Appearance is local UI preference, not server state — the console
            theme/density/locale live in the client, so there is nothing to
            fetch or persist through the API here. */}
        {active === 'appearance' && <AppearancePane />}
        {active === 'about' && <AboutPane />}
      </div>
    </>
  )
}
