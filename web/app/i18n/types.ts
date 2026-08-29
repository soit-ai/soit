import { LanguagesArr } from './language'

// Define types for all translation files
type TranslationKeys = {
  agent: typeof import('./en-US/agent').default
  common: typeof import('./en-US/common').default
  layout: typeof import('./en-US/layout').default
  login: typeof import('./en-US/login').default
  model: typeof import('./en-US/model').default
  chat: typeof import('./en-US/chat').default
  console: typeof import('./en-US/console').default
  knowledge: typeof import('./en-US/knowledge').default
  observe: typeof import('./en-US/observe').default
  run: typeof import('./en-US/run').default
  plugin: typeof import('./en-US/plugin').default
  tools: typeof import('./en-US/tools').default
  register: typeof import('./en-US/register').default
  workflow: typeof import('./en-US/workflow').default
  system: typeof import('./en-US/system').default
  store: typeof import('./en-US/store').default
  safe: typeof import('./en-US/safe').default
  notification: typeof import('./en-US/notification').default
  task: typeof import('./en-US/task').default
}

// Convert nested objects to dot-separated string paths
type DotPrefix<T extends string> = T extends '' ? '' : `.${T}`

type DotNotation<T> = (
  T extends object ?
    {
      [K in Exclude<keyof T, symbol>]: `${K}${DotPrefix<DotNotation<T[K]>>}`
    }[Exclude<keyof T, symbol>]
    : ''
) extends infer D ? Extract<D, string> : never

// Generate all possible translation keys, all keys need namespace
export type TranslationKey = {
  [K in keyof TranslationKeys]: `${K}.${DotNotation<TranslationKeys[K]>}`
}[keyof TranslationKeys]

// Define language type
export type Locale = (typeof LanguagesArr)[number]

// Define translation function type
export type TFunction = (key: TranslationKey, options?: any) => string

// Define return type for useTranslation hook
export interface UseTranslationResponse {
  t: TFunction
  i18n: {
    language: Locale
    changeLanguage: (lng: Locale) => Promise<void>
  }
} 
