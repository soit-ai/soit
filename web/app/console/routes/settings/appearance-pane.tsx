import { useState } from 'react'

import { getLocaleOnClient, setLocaleOnClient, useTranslation, type Locale } from '@/i18n'
import { useConsoleTheme, type ConsoleTheme } from '../../shell/console-theme'

/**
 * Theme and language apply at once and are kept in this browser. Density and
 * timestamp format have one setting each so far, so they are shown, not
 * offered.
 */
export function AppearancePane() {
  const { t } = useTranslation()
  const { theme, setTheme } = useConsoleTheme()
  const [locale, setLocale] = useState<Locale>(getLocaleOnClient)

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>{t('console.settings.appearance')}</h2>
      </div>
      <div className="frow">
        <label htmlFor="appearance-theme">
          {t('console.settings.appearancePane.theme')}
          <small>{t('console.settings.appearancePane.themeHint')}</small>
        </label>
        <select
          id="appearance-theme"
          className="input"
          style={{ maxWidth: 220 }}
          value={theme}
          onChange={(event) => setTheme(event.target.value as ConsoleTheme)}
        >
          <option value="dark">{t('console.settings.appearancePane.themeOptions.dark')}</option>
          <option value="light">{t('console.settings.appearancePane.themeOptions.light')}</option>
        </select>
      </div>
      <div className="frow">
        <label htmlFor="appearance-density">{t('console.settings.appearancePane.density')}</label>
        <select
          id="appearance-density"
          className="input"
          style={{ maxWidth: 220 }}
          disabled
          title={t('console.common.notAvailable')}
        >
          <option>{t('console.settings.appearancePane.densityOptions.comfortable')}</option>
        </select>
      </div>
      <div className="frow">
        <label htmlFor="appearance-language">{t('console.settings.appearancePane.language')}</label>
        <select
          id="appearance-language"
          className="input"
          style={{ maxWidth: 220 }}
          value={locale}
          onChange={(event) => {
            const next = event.target.value as Locale
            setLocale(next)
            void setLocaleOnClient(next)
          }}
        >
          <option value="en-US">{t('console.settings.appearancePane.languageOptions.en-US')}</option>
          <option value="zh-CN">{t('console.settings.appearancePane.languageOptions.zh-CN')}</option>
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
        <label htmlFor="appearance-timestamps">{t('console.settings.appearancePane.timestamps')}</label>
        <select
          id="appearance-timestamps"
          className="input"
          style={{ maxWidth: 220 }}
          disabled
          title={t('console.common.notAvailable')}
        >
          <option>{t('console.settings.appearancePane.timestampOptions.utc')}</option>
        </select>
      </div>
    </div>
  )
}
