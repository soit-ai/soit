import { Navigate, useLocation, useParams } from 'react-router'

import { ConsoleButton, KeyValueList, StatTile, StatusChip } from '../components'
import { useConsoleNavigate } from '../shell/use-console-navigate'
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

// BACKEND-PENDING: workspace/member/api-key services replace the fixtures.
const MOCK_MEMBERS = [
  { name: 'Jude', sub: 'zzpd106@gmail.com', role: 'owner', role_default: true, tfa: { status: 'pass', label: 'ON' }, last: 'now', action: null },
  { name: 'Wei', sub: 'wei@acme.io', role: 'admin', tfa: { status: 'pass', label: 'ON' }, last: '4m ago', action: 'changeRole' },
  { name: 'Ming', sub: 'ming@acme.io', role: 'member', tfa: { status: 'warn', label: 'OFF' }, last: '2d ago', action: 'changeRole' },
  { name: 'audit-bot', sub: 'service account', role: 'read-only', tfa: { status: 'info', label: 'N/A' }, last: '1h ago', action: 'rotateToken' },
  { name: 'sre-oncall@acme.io', invited: true, sub: 'invited 2d ago by Wei', role: 'member', tfa: { status: 'info', label: 'PENDING' }, last: '—', action: 'resendInvite' },
] as const

const MOCK_KEYS = [
  { name: 'ci-pipeline', key: 'sk-soit-…9f2c', scopes: ['runs.read', 'agents.invoke'], created: '08-12', last: 'just now', stale: false },
  { name: 'helpdesk-webhook', key: 'sk-soit-…4ab1', scopes: ['events.write'], created: '07-30', last: '13:47Z', stale: false },
  { name: 'evidence-export', key: 'sk-soit-…77e0', scopes: ['evidence.read'], created: '06-18', last: '62d ago', stale: true },
]

export default function ConsoleSettings() {
  const { t } = useTranslation()
  const { section } = useParams<{ section?: string }>()
  const location = useLocation()
  const navigate = useConsoleNavigate()

  if (!section) {
    return <Navigate to={`/v2/settings/account${location.search}`} replace />
  }
  const active = (SECTIONS as string[]).includes(section) ? (section as SettingsSection) : 'account'

  return (
    <>
      <div className="page-head">
        <h1>{t('console.settings.title')}</h1>
        <p>{t('console.settings.description')}</p>
      </div>
      <div style={{ maxWidth: 860 }}>
        {active === 'account' && (
          <div className="panel">
            <div className="panel-head">
              <h2>{t('console.settings.account')}</h2>
            </div>
            <div className="frow">
              <label>
                {t('console.settings.accountPane.displayName')}
                <small>{t('console.settings.accountPane.displayNameHint')}</small>
              </label>
              <input className="input" defaultValue="Jude" />
            </div>
            <div className="frow">
              <label>{t('console.settings.accountPane.email')}</label>
              <input className="input" defaultValue="zzpd106@gmail.com" disabled />
            </div>
            <div className="frow">
              <label>{t('console.settings.accountPane.role')}</label>
              <div>
                <span className="chip">
                  <i style={{ background: 'var(--primary)' }} />
                  owner
                </span>
              </div>
            </div>
            <div className="frow">
              <label>{t('console.settings.accountPane.twoFactor')}</label>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <StatusChip status="pass" label="ENABLED" />
                <ConsoleButton style={{ height: 24, fontSize: 11 }}>
                  {t('console.settings.accountPane.manageDevices')}
                </ConsoleButton>
              </div>
            </div>
            <div className="frow">
              <label style={{ color: 'var(--danger-foreground)' }}>
                {t('console.settings.accountPane.del')}
                <small>{t('console.settings.accountPane.delHint')}</small>
              </label>
              <div>
                <ConsoleButton style={{ color: 'var(--danger-foreground)' }}>
                  {t('console.settings.accountPane.delBtn')}
                </ConsoleButton>
              </div>
            </div>
          </div>
        )}

        {active === 'team' && (
          <div className="panel">
            <div className="panel-head">
              <h2>{t('console.settings.team')}</h2>
              <span className="hint">{t('console.settings.teamPane.hint')}</span>
              <span className="more">
                <ConsoleButton variant="primary" style={{ height: 24, fontSize: 11 }}>
                  {t('console.settings.teamPane.invite')}
                </ConsoleButton>
              </span>
            </div>
            <table>
              <thead>
                <tr>
                  <th>{t('console.settings.teamPane.columns.member')}</th>
                  <th>{t('console.settings.teamPane.columns.role')}</th>
                  <th>{t('console.settings.teamPane.columns.twoFactor')}</th>
                  <th className="num">{t('console.settings.teamPane.columns.lastActive')}</th>
                  <th className="num" />
                </tr>
              </thead>
              <tbody>
                {MOCK_MEMBERS.map((member) => (
                  <tr key={member.name}>
                    <td>
                      {'invited' in member && member.invited ? (
                        <span className="dim">{member.name}</span>
                      ) : (
                        <b style={{ fontWeight: 600 }}>{member.name}</b>
                      )}
                      <br />
                      <span className="dimmer" style={{ fontSize: 10.5 }}>
                        {member.sub}
                      </span>
                    </td>
                    <td>
                      <span className="chip">
                        {'role_default' in member && member.role_default && (
                          <i style={{ background: 'var(--primary)' }} />
                        )}
                        {member.role}
                      </span>
                    </td>
                    <td>
                      <StatusChip status={member.tfa.status} label={member.tfa.label} />
                    </td>
                    <td className="num dimmer">{member.last}</td>
                    <td className="num">
                      {member.action && (
                        <ConsoleButton variant="ghost" style={{ height: 22, fontSize: 10.5 }}>
                          {member.action === 'changeRole'
                            ? t('console.settings.teamPane.changeRole')
                            : member.action === 'rotateToken'
                              ? t('console.settings.teamPane.rotateToken')
                              : t('console.settings.teamPane.resendInvite')}
                        </ConsoleButton>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="pager">
              <span>{t('console.settings.teamPane.note')}</span>
            </div>
          </div>
        )}

        {active === 'api' && (
          <div className="panel">
            <div className="panel-head">
              <h2>{t('console.settings.api')}</h2>
              <span className="hint">{t('console.settings.apiPane.hint')}</span>
              <span className="more">
                <ConsoleButton variant="primary" style={{ height: 24, fontSize: 11 }}>
                  {t('console.settings.apiPane.create')}
                </ConsoleButton>
              </span>
            </div>
            <table>
              <thead>
                <tr>
                  <th>{t('console.settings.apiPane.columns.name')}</th>
                  <th>{t('console.settings.apiPane.columns.key')}</th>
                  <th>{t('console.settings.apiPane.columns.scopes')}</th>
                  <th className="num">{t('console.settings.apiPane.columns.created')}</th>
                  <th className="num">{t('console.settings.apiPane.columns.lastUsed')}</th>
                  <th className="num" />
                </tr>
              </thead>
              <tbody>
                {MOCK_KEYS.map((key) => (
                  <tr key={key.name}>
                    <td>
                      <b style={{ fontWeight: 600 }}>{key.name}</b>
                    </td>
                    <td className="mono dim">{key.key}</td>
                    <td>
                      <span className="scopes">
                        {key.scopes.map((scope) => (
                          <span key={scope} className="chip">
                            {scope}
                          </span>
                        ))}
                      </span>
                    </td>
                    <td className="num dimmer">{key.created}</td>
                    <td className="num" style={key.stale ? { color: 'var(--warning-foreground)' } : undefined}>
                      {key.stale ? key.last : <span className="dimmer">{key.last}</span>}
                    </td>
                    <td className="num">
                      <ConsoleButton
                        variant="ghost"
                        style={{ height: 22, fontSize: 10.5, color: 'var(--danger-foreground)' }}
                      >
                        {t('console.settings.apiPane.revoke')}
                      </ConsoleButton>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="pager">
              <span>{t('console.settings.apiPane.note')}</span>
            </div>
          </div>
        )}

        {active === 'security' && (
          <div className="panel">
            <div className="panel-head">
              <h2>{t('console.settings.security')}</h2>
            </div>
            <div className="frow">
              <label>
                {t('console.settings.securityPane.twoFactorPolicy')}
                <small>{t('console.settings.securityPane.twoFactorPolicyHint')}</small>
              </label>
              <select className="input" style={{ maxWidth: 280 }} defaultValue="required for admin & owner">
                <option>required for admin &amp; owner</option>
                <option>required for everyone</option>
                <option>optional</option>
              </select>
            </div>
            <div className="frow">
              <label>
                {t('console.settings.securityPane.sso')}
                <small>{t('console.settings.securityPane.ssoHint')}</small>
              </label>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <StatusChip status="info" label="NOT CONFIGURED" />
                <ConsoleButton style={{ height: 24, fontSize: 11 }}>
                  {t('console.settings.securityPane.configureSso')}
                </ConsoleButton>
              </div>
            </div>
            <div className="frow">
              <label>{t('console.settings.securityPane.sessionTimeout')}</label>
              <select className="input" style={{ maxWidth: 200 }} defaultValue="12 hours">
                <option>12 hours</option>
                <option>24 hours</option>
                <option>7 days</option>
              </select>
            </div>
            <div className="frow">
              <label>
                {t('console.settings.securityPane.ipAllowlist')}
                <small>{t('console.settings.securityPane.ipAllowlistHint')}</small>
              </label>
              <textarea className="input" defaultValue={'10.0.0.0/8\n203.0.113.0/24'} />
            </div>
            <div className="frow">
              <label>{t('console.settings.securityPane.auditAccess')}</label>
              <select className="input" style={{ maxWidth: 280 }} defaultValue="owner & admin">
                <option>owner &amp; admin</option>
                <option>owner only</option>
                <option>all members · read-only</option>
              </select>
            </div>
            <div className="frow">
              <label style={{ color: 'var(--danger-foreground)' }}>
                {t('console.settings.securityPane.sessions')}
                <small>{t('console.settings.securityPane.sessionsHint')}</small>
              </label>
              <div>
                <ConsoleButton style={{ color: 'var(--danger-foreground)' }}>
                  {t('console.settings.securityPane.signOutAll')}
                </ConsoleButton>
              </div>
            </div>
          </div>
        )}

        {active === 'secrets' && (
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
                onClick={() => navigate('/v2/govern/secrets')}
              >
                {t('console.settings.secretsPane.open')}
              </ConsoleButton>
            </div>
          </div>
        )}

        {active === 'notifications' && (
          <div className="panel">
            <div className="panel-head">
              <h2>{t('console.settings.notifications')}</h2>
              <span className="hint">{t('console.settings.notificationsPane.hint')}</span>
            </div>
            <div className="frow">
              <label>
                {t('console.settings.notificationsPane.approvals')}
                <small>{t('console.settings.notificationsPane.approvalsHint')}</small>
              </label>
              <div className="checks">
                <label>
                  <input type="checkbox" defaultChecked />
                  Email · immediately
                </label>
                <label>
                  <input type="checkbox" defaultChecked />
                  Slack · #governance
                </label>
              </div>
            </div>
            <div className="frow">
              <label>{t('console.settings.notificationsPane.policyBlocks')}</label>
              <div className="checks">
                <label>
                  <input type="checkbox" defaultChecked />
                  Slack · #governance
                </label>
                <label>
                  <input type="checkbox" />
                  Email · hourly digest
                </label>
              </div>
            </div>
            <div className="frow">
              <label>{t('console.settings.notificationsPane.budget')}</label>
              <div className="checks">
                <label>
                  <input type="checkbox" defaultChecked />
                  Slack · #finance-ops at 80%
                </label>
                <label>
                  <input type="checkbox" defaultChecked />
                  Email at 100%
                </label>
              </div>
            </div>
            <div className="frow">
              <label>{t('console.settings.notificationsPane.taskFailures')}</label>
              <div className="checks">
                <label>
                  <input type="checkbox" defaultChecked />
                  Slack · per task &quot;on failure&quot; channel
                </label>
              </div>
            </div>
            <div className="frow">
              <label>
                {t('console.settings.notificationsPane.digest')}
                <small>{t('console.settings.notificationsPane.digestHint')}</small>
              </label>
              <div className="checks">
                <label>
                  <input type="checkbox" defaultChecked />
                  Email · Monday 09:00Z
                </label>
              </div>
            </div>
          </div>
        )}

        {active === 'billing' && (
          <>
            <div className="tiles" style={{ gridTemplateColumns: 'repeat(3,1fr)' }}>
              <StatTile
                label={t('console.settings.billingPane.edition')}
                value={<span style={{ fontSize: 15 }}>Enterprise</span>}
                sub={<span className="mono dimmer">self-hosted · annual license</span>}
              />
              <StatTile
                label={t('console.settings.billingPane.seats')}
                value="4 / 25"
                sub={<span className="mono dimmer">renewal 2027-03-01</span>}
              />
              <StatTile
                label={t('console.settings.billingPane.spend')}
                value="$612.40"
                sub={<span className="mono dimmer">budget $3,600 · 17%</span>}
              />
            </div>
            <div className="panel">
              <div className="panel-head">
                <h2>{t('console.settings.billingPane.invoices')}</h2>
                <span className="hint">{t('console.settings.billingPane.invoicesHint')}</span>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>{t('console.settings.billingPane.columns.invoice')}</th>
                    <th>{t('console.settings.billingPane.columns.period')}</th>
                    <th className="num">{t('console.settings.billingPane.columns.amount')}</th>
                    <th>{t('console.settings.billingPane.columns.status')}</th>
                    <th className="num" />
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="mono">INV-2026-0301</td>
                    <td className="dim">2026-03 → 2027-03 · license</td>
                    <td className="num dim">$18,000.00</td>
                    <td>
                      <StatusChip status="pass" label="PAID" />
                    </td>
                    <td className="num">
                      <ConsoleButton variant="ghost" style={{ height: 22, fontSize: 10.5 }}>
                        {t('console.settings.billingPane.pdf')}
                      </ConsoleButton>
                    </td>
                  </tr>
                  <tr>
                    <td className="mono">INV-2026-0117</td>
                    <td className="dim">onboarding support</td>
                    <td className="num dim">$2,400.00</td>
                    <td>
                      <StatusChip status="pass" label="PAID" />
                    </td>
                    <td className="num">
                      <ConsoleButton variant="ghost" style={{ height: 22, fontSize: 10.5 }}>
                        {t('console.settings.billingPane.pdf')}
                      </ConsoleButton>
                    </td>
                  </tr>
                </tbody>
              </table>
              <div className="pager">
                <span>{t('console.settings.billingPane.note')}</span>
              </div>
            </div>
          </>
        )}

        {active === 'appearance' && (
          <div className="panel">
            <div className="panel-head">
              <h2>{t('console.settings.appearance')}</h2>
            </div>
            <div className="frow">
              <label>
                {t('console.settings.appearancePane.theme')}
                <small>{t('console.settings.appearancePane.themeHint')}</small>
              </label>
              <select className="input" style={{ maxWidth: 220 }} defaultValue="dark · default">
                <option>dark · default</option>
                <option>light</option>
                <option>follow system</option>
              </select>
            </div>
            <div className="frow">
              <label>{t('console.settings.appearancePane.density')}</label>
              <select className="input" style={{ maxWidth: 220 }} defaultValue="comfortable">
                <option>comfortable</option>
                <option>compact</option>
              </select>
            </div>
            <div className="frow">
              <label>{t('console.settings.appearancePane.language')}</label>
              <select className="input" style={{ maxWidth: 220 }} defaultValue="English">
                <option>English</option>
                <option>Chinese (Simplified)</option>
              </select>
            </div>
            <div className="frow">
              <label>
                {t('console.settings.appearancePane.accent')}
                <small>{t('console.settings.appearancePane.accentHint')}</small>
              </label>
              <div>
                <span className="chip">
                  <i style={{ background: 'var(--primary)' }} />
                  Signal Blue · fixed
                </span>
              </div>
            </div>
            <div className="frow">
              <label>{t('console.settings.appearancePane.timestamps')}</label>
              <select className="input" style={{ maxWidth: 220 }} defaultValue="UTC · absolute">
                <option>UTC · absolute</option>
                <option>local · relative</option>
              </select>
            </div>
          </div>
        )}

        {active === 'about' && (
          <div className="panel">
            <div className="panel-head">
              <h2>{t('console.settings.about')}</h2>
            </div>
            <KeyValueList
              items={[
                { key: t('console.settings.aboutPane.console'), value: 'v1.0.3 · build 8f31c2ae' },
                { key: t('console.settings.aboutPane.runtime'), value: 'soit-server v1.0.3' },
                { key: t('console.settings.aboutPane.policyEngine'), value: 'v0.9.1 · bundle schema 3' },
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
        )}
      </div>
    </>
  )
}
