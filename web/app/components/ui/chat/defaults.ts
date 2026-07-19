export const DEFAULT_CHAT_PROVIDER = 'deepseek'
export const DEFAULT_DEEP_THINKING_MODEL = 'deepseek-reasoner'
export const DEFAULT_STANDARD_MODEL = 'deepseek-chat'

const CHAT_WEB_SEARCH_KEY = 'chat_web_search'
const CHAT_CODE_INTERPRETER_KEY = 'chat_code_interpreter'

export const isDeepThinkingEnabled = (): boolean => {
  if (typeof window === 'undefined') {
    return false
  }
  return localStorage.getItem('chat_deep_thinking') === '1'
}

export const isWebSearchEnabled = (): boolean => {
  if (typeof window === 'undefined') {
    return false
  }
  return localStorage.getItem(CHAT_WEB_SEARCH_KEY) === '1'
}

export const isCodeInterpreterEnabled = (): boolean => {
  if (typeof window === 'undefined') {
    return false
  }
  return localStorage.getItem(CHAT_CODE_INTERPRETER_KEY) === '1'
}

export const setWebSearchEnabled = (enabled: boolean): void => {
  if (typeof window !== 'undefined') {
    localStorage.setItem(CHAT_WEB_SEARCH_KEY, enabled ? '1' : '0')
  }
}

export const setCodeInterpreterEnabled = (enabled: boolean): void => {
  if (typeof window !== 'undefined') {
    localStorage.setItem(CHAT_CODE_INTERPRETER_KEY, enabled ? '1' : '0')
  }
}

export const resolveDefaultChatModel = (deepThinkingEnabled: boolean): string => {
  return deepThinkingEnabled ? DEFAULT_DEEP_THINKING_MODEL : DEFAULT_STANDARD_MODEL
}

export const resolveStoredChatProvider = (): string => {
  if (typeof window === 'undefined') {
    return DEFAULT_CHAT_PROVIDER
  }
  return localStorage.getItem('chat_default_provider') || DEFAULT_CHAT_PROVIDER
}

export const resolveStoredChatModel = (): string => {
  if (typeof window === 'undefined') {
    return DEFAULT_STANDARD_MODEL
  }
  const storedModel = localStorage.getItem('chat_default_model')
  if (storedModel) {
    if (storedModel === 'deepseek-r1:8b') {
      return DEFAULT_DEEP_THINKING_MODEL
    }
    return storedModel
  }
  return resolveDefaultChatModel(isDeepThinkingEnabled())
}

export const resolveRuntimeChatModel = (
  model: string | null | undefined,
  deepThinkingEnabled: boolean
): string => {
  const fallback = resolveDefaultChatModel(deepThinkingEnabled)
  const candidate = model || resolveStoredChatModel()
  if (!candidate) {
    return fallback
  }
  if (
    candidate === DEFAULT_STANDARD_MODEL ||
    candidate === DEFAULT_DEEP_THINKING_MODEL
  ) {
    return fallback
  }
  return candidate
}
