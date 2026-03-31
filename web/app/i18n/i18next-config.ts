import i18next from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { LanguagesArr } from '@/i18n/language'
import type { Locale, TFunction, UseTranslationResponse } from './types'

type ResourceType = {
  translation: {
    [key: string]: any
  }
}

type ResourcesType = {
  [key: string]: ResourceType
}

// Load language resources on demand
const loadLangResources = async (lang: string): Promise<ResourceType | null> => {
  try {
    const resources = {
      translation: {
        agent: (await import(`./${lang}/agent.ts`)).default,
        app: (await import(`./${lang}/app.ts`)).default,
        chat: (await import(`./${lang}/chat.ts`)).default,
        common: (await import(`./${lang}/common.ts`)).default,
        knowledge: (await import(`./${lang}/knowledge.ts`)).default,
        layout: (await import(`./${lang}/layout.ts`)).default,
        login: (await import(`./${lang}/login.ts`)).default,
        run: (await import(`./${lang}/run.ts`)).default,
        plugin: (await import(`./${lang}/plugin.ts`)).default,
        tools: (await import(`./${lang}/tools.ts`)).default,
        register: (await import(`./${lang}/register.ts`)).default,
        workflow: (await import(`./${lang}/workflow.ts`)).default,
        system: (await import(`./${lang}/system.ts`)).default,
        store: (await import(`./${lang}/store.ts`)).default,
        safe: (await import(`./${lang}/safe.ts`)).default,
        notification: (await import(`./${lang}/notification.ts`)).default,
      },
    }
    return resources
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
  let userLang = localStorage.getItem('i18nextLng') || localStorage.getItem('locale')
  
  // Load both user language and default language when they differ.
  if (userLang && userLang !== defaultLang && LanguagesArr.includes(userLang as Locale)) {
    // Load user language resources.
    const userResources = await loadLangResources(userLang)
    if (userResources) {
      resources[userLang] = userResources
      console.log(`Loaded user language resources: ${userLang}`)
    }
  }
  
  // Always load default language resources as fallback.
  const defaultResources = await loadLangResources(defaultLang)
  if (defaultResources) {
    resources[defaultLang] = defaultResources
    console.log(`Loaded default language resources: ${defaultLang}`)
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
      console.log('i18next initialized')
    }
  )

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

export const useTranslation = (ns = ['translation'], options = {}): UseTranslationResponse => {
  return {
    t: i18next.t as TFunction,
    i18n: {
      language: i18next.language as Locale,
      changeLanguage: async (lng: Locale) => {
        await i18next.changeLanguage(lng)
      },
    },
  }
}
