import { changeLanguage as _changeLanguage, useTranslation as _useTranslation } from '@/i18n/i18next-config'
import { LanguagesArr } from '@/i18n/language'

export const i18n = {
  defaultLocale: 'en-US',
  locales: LanguagesArr,
} as const

export type Locale = (typeof i18n)['locales'][number]

// Read the current language setting
export const getLocaleOnClient = (): Locale => {
  const savedLocale = localStorage.getItem('i18nextLng')
  // Use the stored language when it is present and supported.
  if (savedLocale && i18n.locales.includes(savedLocale as Locale)) {
    return savedLocale as Locale
  }

  // Fall back to the legacy `locale` key.
  const localeSetting = localStorage.getItem('locale')
  if (localeSetting && i18n.locales.includes(localeSetting as Locale)) {
    // Mirror it back to i18nextLng.
    localStorage.setItem('i18nextLng', localeSetting)
    return localeSetting as Locale
  }

  // Nothing stored: fall back to the default language.
  return i18n.defaultLocale
}

// Change the language without reloading the page
export const setLocaleOnClient = async (locale: Locale) => {
  if (!i18n.locales.includes(locale)) {
    console.warn(`Invalid locale: ${locale}, falling back to ${i18n.defaultLocale}`)
    locale = i18n.defaultLocale
  }
  
  try {
    await _changeLanguage(locale)
    localStorage.setItem('i18nextLng', locale)
    localStorage.setItem('locale', locale)
  } catch (error) {
    console.error('Failed to change language:', error)
  }
}

// Re-export the type-safe translation helpers
export const changeLanguage = _changeLanguage
export const useTranslation = _useTranslation
