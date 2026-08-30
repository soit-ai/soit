import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { Toaster } from 'sonner'

const queryClient = new QueryClient()

/**
 * The pre-rebuild `ThemeProvider` is deliberately not mounted here. Its only
 * remaining effect was to write `light` onto the document element on mount,
 * after `ConsoleThemeProvider` had already written the console's own choice --
 * so a dark console kept a light page canvas. Everything that read its context
 * lives under `app/routes_old/`, which the route table no longer serves.
 */
export default function AppProviders({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster position="top-right" expand closeButton />
    </QueryClientProvider>
  )
}
