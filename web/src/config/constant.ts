// Constant enums.

// Empty image enum.
export enum EmptyImage {
  EMPTY_BOX = '@/assets/images/empty_box.png',
}

// Theme enum.
export enum Theme {
  LIGHT = 'light',
  DARK = 'dark',
}

// Model enum.
export enum Model {
  'GPT-3.5-Turbo' = 'gpt-3.5-turbo',
  'GPT-3.5-Turbo-0301' = 'gpt-3.5-turbo-0301',
  'GPT-3.5-Turbo-0613' = 'gpt-3.5-turbo-0613',
  'GPT-3.5-Turbo-16k' = 'gpt-3.5-turbo-16k',
  'GPT-4' = 'gpt-4',
  'GPT-4-0314' = 'gpt-4-0314',
  'GPT-4-0613' = 'gpt-4-0613',
  'GPT-4-32k' = 'gpt-4-32k',
  'GPT-4-32k-0314' = 'gpt-4-32k-0314',
  'GPT-4-32k-0613' = 'gpt-4-32k-0613',
  'GPT-4-Mobile' = 'gpt-4-mobile',
}

// Model list.
export const ModelList = [
  {
    label: 'GPT-3.5-Turbo',
    value: Model['GPT-3.5-Turbo'],
  },
  {
    label: 'GPT-3.5-Turbo-16k',
    value: Model['GPT-3.5-Turbo-16k'],
  },
  {
    label: 'GPT-3.5-Turbo-0301',
    value: Model['GPT-3.5-Turbo-0301'],
  },
  {
    label: 'GPT-3.5-Turbo-0613',
    value: Model['GPT-3.5-Turbo-0613'],
  },
  {
    label: 'GPT-4',
    value: Model['GPT-4'],
  },
  {
    label: 'GPT-4-0314',
    value: Model['GPT-4-0314'],
  },
  {
    label: 'GPT-4-0613',
    value: Model['GPT-4-0613'],
  },
  {
    label: 'GPT-4-32k',
    value: Model['GPT-4-32k'],
  },
  {
    label: 'GPT-4-32k-0314',
    value: Model['GPT-4-32k-0314'],
  },
  {
    label: 'GPT-4-32k-0613',
    value: Model['GPT-4-32k-0613'],
  },
  {
    label: 'GPT-4-Mobile',
    value: Model['GPT-4-Mobile'],
  },
]

// Enter key enum.
export enum EnterKey {
  ENTER = 'enter',
  CTRL_ENTER = 'ctrl.enter',
  SHIFT_ENTER = 'shift.enter',
  ALT_ENTER = 'alt.enter',
}

// Enter key list.
export const EnterKeyList = [
  {
    label: 'ENTER',
    value: EnterKey.ENTER,
  },
  {
    label: 'CTRL + ENTER',
    value: EnterKey.CTRL_ENTER,
  },
  {
    label: 'SHIFT + ENTER',
    value: EnterKey.SHIFT_ENTER,
  },
  {
    label: 'ALT + ENTER',
    value: EnterKey.ALT_ENTER,
  },
]

// Language enum.
export enum Language {
  ZH_CN = 'zh_CN',
  EN_US = 'en_US',
  ZH_TW = 'zh_TW',
  FR_FR = 'fr_FR',
  ES_ES = 'es_ES',
  IT_IT = 'it_IT',
  TR_TR = 'tr_TR',
  JA_JP = 'ja_JP',
  DE_DE = 'de_DE',
  VI_VN = 'vi_VN',
  RU_RU = 'ru_RU',
  CS_CZ = 'cs_CZ',
  KO_KR = 'ko_KR',
}

// Language list.
export const LanguageList = [
  {
    label: '简体中文',
    value: Language.ZH_CN,
  },
  {
    label: '繁体中文',
    value: Language.ZH_TW,
  },
  {
    label: 'English',
    value: Language.EN_US,
  },
  {
    label: 'Français',
    value: Language.FR_FR,
  },
  {
    label: 'Español',
    value: Language.ES_ES,
  },
  {
    label: 'Italiano',
    value: Language.IT_IT,
  },
  {
    label: 'Türkçe',
    value: Language.TR_TR,
  },
  {
    label: '日本語',
    value: Language.JA_JP,
  },
  {
    label: 'Deutsch',
    value: Language.DE_DE,
  },
  {
    label: 'Tiếng Việt',
    value: Language.VI_VN,
  },
  {
    label: 'Русский',
    value: Language.RU_RU,
  },
  {
    label: 'Čeština',
    value: Language.CS_CZ,
  },
  {
    label: '한국어',
    value: Language.KO_KR,
  },
]

