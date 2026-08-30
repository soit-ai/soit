import { createContext, useCallback, useContext, useEffect, useState } from 'react'

/**
 * Console theme is independent from the legacy tree: its own storage key and
 * a container-level `.dark` class on the console root (app.css declares the
 * dark variant as an ancestor-class selector, so scoping works). The console
 * defaults to dark.
 *
 * The container class alone does not reach the page canvas, which `app.css`
 * paints from `body` and `.dark body`, so the theme is mirrored onto the
 * document element as well. This provider is the only writer of that class:
 * the pre-rebuild `ThemeProvider` that used to own it defaulted to light and
 * knew nothing about the console's choice.
 */
export type ConsoleTheme = 'dark' | 'light'

export const CONSOLE_THEME_STORAGE_KEY = 'soit-console-theme'
/** The key the pre-rebuild tree wrote, read once so the switch-over to the
 *  console at the root does not silently discard an existing preference. */
const LEGACY_THEME_STORAGE_KEY = 'vite-ui-theme'
const DEFAULT_THEME: ConsoleTheme = 'dark'

interface ConsoleThemeState {
  theme: ConsoleTheme
  setTheme: (theme: ConsoleTheme) => void
  toggleTheme: () => void
}

const ConsoleThemeContext = createContext<ConsoleThemeState>({
  theme: DEFAULT_THEME,
  setTheme: () => null,
  toggleTheme: () => null,
})

function readStoredTheme(): ConsoleTheme {
  if (typeof window === 'undefined') return DEFAULT_THEME
  const stored = window.localStorage.getItem(CONSOLE_THEME_STORAGE_KEY)
  if (stored === 'light' || stored === 'dark') return stored
  // No console preference yet: adopt the legacy one if the user set it there.
  // "system" is not a console theme, so it falls through to the dark default.
  const legacy = window.localStorage.getItem(LEGACY_THEME_STORAGE_KEY)
  if (legacy === 'light' || legacy === 'dark') return legacy
  return DEFAULT_THEME
}

export function ConsoleThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<ConsoleTheme>(readStoredTheme)

  useEffect(() => {
    window.localStorage.setItem(CONSOLE_THEME_STORAGE_KEY, theme)
  }, [theme])

  // The canvas is everything the page's own boxes do not cover: the area above
  // and below a scrolling layout, and the browser's overscroll. Leaving it on
  // the light default put a light band around a dark console -- visible on the
  // auth screens, which scroll, and never on the shell, which fills the
  // viewport. `color-scheme` carries the same choice to native scrollbars and
  // form controls.
  useEffect(() => {
    const root = window.document.documentElement
    root.classList.remove('light', 'dark')
    root.classList.add(theme)
    root.style.colorScheme = theme
  }, [theme])

  const setTheme = useCallback((next: ConsoleTheme) => setThemeState(next), [])
  const toggleTheme = useCallback(
    () => setThemeState((current) => (current === 'dark' ? 'light' : 'dark')),
    [],
  )

  return (
    <ConsoleThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ConsoleThemeContext.Provider>
  )
}

export function useConsoleTheme() {
  return useContext(ConsoleThemeContext)
}
