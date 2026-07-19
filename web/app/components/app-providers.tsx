import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { Toaster } from 'sonner'

import { ThemeProvider } from '@/components/theme-provider'

const queryClient = new QueryClient()

export default function AppProviders({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider defaultTheme="light" storageKey="vite-ui-theme">
        {children}
        <Toaster position="top-right" expand closeButton />
      </ThemeProvider>
    </QueryClientProvider>
  )
}
