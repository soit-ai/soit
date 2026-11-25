import i18next from 'i18next'
import { initReactI18next, useTranslation as useI18nextTranslation } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { LanguagesArr } from '@/i18n/language'
import { debugLog } from '@/utils/debug'
import type { Locale, TFunction, UseTranslationResponse } from './types'

type ResourceType = {
  translation: {
    [key: string]: any
  }
}

type ResourcesType = {
  [key: string]: ResourceType
}

const NAMESPACES = [
  'agent',
  'auth',
  'chat',
  'common',
  'console',
  'knowledge',
  'layout',
  'login',
  'model',
  'observe',
  'run',
  'plugin',
  'tools',
  'register',
  'workflow',
  'system',
  'store',
  'safe',
  'notification',
  'task',
] as const

// Load language resources on demand. The namespaces load in parallel: one
// after another, they held the first render for a chain of round trips.
const loadLangResources = async (lang: string): Promise<ResourceType | null> => {
  try {
    const modules = await Promise.all(
      NAMESPACES.map((namespace) => import(`./${lang}/${namespace}.ts`)),
    )
    const translation: ResourceType['translation'] = {}
    NAMESPACES.forEach((namespace, index) => {
      translation[namespace] = modules[index].default
    })
    return { translation }
  } catch (error) {
    console.error(`Failed to load resources for ${lang}:`, error)
    return null
  }
}

// Load user-selected language resources and default resources.
const initResources = async (): Promise<ResourcesType> => {
  const defaultLang = 'en-US'
  const resources: ResourcesType = {}
  
  // Get user-selected language.
  const userLang = localStorage.getItem('i18nextLng') || localStorage.getItem('locale')
  
  // Load both user language and default language when they differ.
  const wantsUserLang =
    Boolean(userLang) && userLang !== defaultLang && LanguagesArr.includes(userLang as Locale)
  const [userResources, defaultResources] = await Promise.all([
    wantsUserLang ? loadLangResources(userLang as string) : Promise.resolve(null),
    // Always load default language resources as fallback.
    loadLangResources(defaultLang),
  ])
  if (userResources) {
    resources[userLang as string] = userResources
    debugLog(`Loaded user language resources: ${userLang}`)
  }

  if (defaultResources) {
    resources[defaultLang] = defaultResources
    debugLog(`Loaded default language resources: ${defaultLang}`)
  }
  
  return resources
}

// Initialize i18next
i18next
  .use(LanguageDetector)
  .use(initReactI18next)
  .init(
    {
      resources: await initResources(),
      fallbackLng: 'en-US',
      defaultNS: 'translation',
      ns: ['translation'],
      detection: {
        order: ['localStorage', 'navigator'],
        caches: ['localStorage'],
        lookupLocalStorage: 'i18nextLng',
      },
      interpolation: {
        escapeValue: false,
      },
      react: {
        useSuspense: false,
      },
      debug: process.env.NODE_ENV === 'development',
    },
    () => {
      debugLog('i18next initialized')
    }
  )

// Screen readers and the browser's own spelling and hyphenation go by the
// document's language, which root.tsx renders as English.
const syncDocumentLanguage = (lng: string | undefined) => {
  if (lng && typeof document !== 'undefined') document.documentElement.lang = lng
}
i18next.on('languageChanged', syncDocumentLanguage)
syncDocumentLanguage(i18next.language)

// Dynamically load other language resources
export const loadLanguageAsync = async (lang: Locale): Promise<void> => {
  if (i18next.hasResourceBundle(lang, 'translation')) {
    return
  }

  const resources = await loadLangResources(lang)
  if (resources) {
    i18next.addResourceBundle(lang, 'translation', resources.translation, true, true)
  }
}

export default i18next

export const changeLanguage = async (lang: Locale): Promise<void> => {
  await loadLanguageAsync(lang)
  await i18next.changeLanguage(lang)
}

/**
 * react-i18next's hook under the project's typed `t`. It subscribes the
 * component to language changes; returning `i18next.t` directly did not, so
 * switching the language changed nothing until something else re-rendered.
 */
export const useTranslation = (): UseTranslationResponse => {
  const { t, i18n } = useI18nextTranslation()
  return {
    t: t as unknown as TFunction,
    i18n: {
      language: i18n.language as Locale,
      changeLanguage,
    },
  }
}
