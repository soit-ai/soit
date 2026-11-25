import { MutationCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { Toaster } from 'sonner'

/**
 * Any successful write may change a figure the shell shows on every page:
 * the navigation counts and the context panel. Those queries live in their
 * own key families and are cheap, so a write marks them stale and the visible
 * ones refetch, instead of each page remembering which counts its write moves
 * (they waited out a 60 second stale time before).
 */
const queryClient: QueryClient = new QueryClient({
  mutationCache: new MutationCache({
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['console', 'counts'] })
      void queryClient.invalidateQueries({ queryKey: ['console', 'panel'] })
    },
  }),
})

/**
 * The pre-rebuild `ThemeProvider` is deliberately not mounted here. Its only
 * remaining effect was to write `light` onto the document element on mount,
 * after `ConsoleThemeProvider` had already written the console's own choice --
 * so a dark console kept a light page canvas. Everything that read its context
 * was in the pre-rebuild route tree, which is gone.
 */
export default function AppProviders({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster position="top-right" expand closeButton />
    </QueryClientProvider>
  )
}
