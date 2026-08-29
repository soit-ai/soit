import { Outlet } from 'react-router'

import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import '@/console/styles/console.css'

import { cn } from '@/lib/utils'

import { ConsoleThemeProvider, useConsoleTheme } from './console-theme'

function ConsoleRoot() {
  const { theme } = useConsoleTheme()

  return (
    <div
      className={cn(
        'console-root flex h-dvh min-w-0 flex-col overflow-hidden bg-background text-foreground',
        theme === 'dark' && 'dark',
      )}
    >
      <main className="console-glow min-h-0 flex-1 overflow-y-auto px-6 pb-12 pt-6">
        <Outlet />
      </main>
    </div>
  )
}

export default function ConsoleLayout() {
  return (
    <ConsoleThemeProvider>
      <ConsoleRoot />
    </ConsoleThemeProvider>
  )
}
