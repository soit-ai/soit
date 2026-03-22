import { changeLanguage as _changeLanguage, useTranslation as _useTranslation } from '@/i18n/i18next-config'
import { LanguagesArr } from '@/i18n/language'

export const i18n = {
  defaultLocale: 'en-US',
  locales: LanguagesArr,
} as const

export type Locale = (typeof i18n)['locales'][number]

// 获取当前语言设置
export const getLocaleOnClient = (): Locale => {
  const savedLocale = localStorage.getItem('i18nextLng')
  // 如果在localStorage中找到了语言设置并且是支持的语言，则使用它
  if (savedLocale && i18n.locales.includes(savedLocale as Locale)) {
    return savedLocale as Locale
  }
  
  // 尝试从locale键获取
  const localeSetting = localStorage.getItem('locale')
  if (localeSetting && i18n.locales.includes(localeSetting as Locale)) {
    // 同步到i18nextLng
    localStorage.setItem('i18nextLng', localeSetting)
    return localeSetting as Locale
  }
  
  // 如果都没有找到，返回默认语言
  return i18n.defaultLocale
}

// 设置语言，不刷新页面
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

// 导出类型安全的翻译函数
export const changeLanguage = _changeLanguage
export const useTranslation = _useTranslation
