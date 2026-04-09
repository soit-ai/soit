import { scan } from 'react-scan' // import this BEFORE react
import { useEffect } from 'react'
import { isRouteErrorResponse, Links, Meta, Outlet, Scripts, ScrollRestoration } from 'react-router'
import { ThemeProvider } from '@/components/theme-provider'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
// import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client'
// import { createWebStoragePersistor } from '@tanstack/react-query-persist-client'
import type { Route } from './+types/root'
import stylesheet from './app.css?url'
import { Toaster } from 'sonner'
import { AssistantModal } from '@/components/ui/chat/assistant-modal'
import { AssistantSidebar } from '@/components/ui/chat/assistant-sidebar'
import { DrawerProvider } from '@/hooks/use-drawer'
const queryClient = new QueryClient()
// const persistor = createWebStoragePersistor({
//   storage: window.localStorage,
// })

export const links: Route.LinksFunction = () => [
  { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
  {
    rel: 'preconnect',
    href: 'https://fonts.gstatic.com',
    crossOrigin: 'anonymous',
  },
  {
    rel: 'stylesheet',
    href: 'https://fonts.googleapis.com/css2?family=Manrope:wght@200..800&display=swap',
  },
  { rel: 'stylesheet', href: stylesheet },
]

export function Layout({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    // Make sure to run react-scan only after hydration
    if (typeof window !== 'undefined') {
      // production mode clear
      if (!import.meta.env.PROD) {
        // scan({
        //   enabled: true,
        //   log: false, // logs render info to console (default: false)
        // })
      }
    }
  }, [])

  return (
    <html lang="en" className="bg-background text-foreground">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>SOIT AI</title>
        <meta name="description" content="SOIT AI" />
        <meta name="keywords" content="SOIT AI, AI, Assistant, Chat, AI Assistant, ChatGPT, Qwen, DeepSeek, Gemini" />
        <meta name="author" content="SOIT AI" />
        <meta name="robots" content="index, follow" />
        <meta name="googlebot" content="index, follow" />
        <meta name="bingbot" content="index, follow" />
        <meta name="alexa" content="index, follow" />
        <Meta />
        <Links />
      </head>
      <body>
        {children}
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  )
}

export default function App() {

  return (
    <ThemeProvider defaultTheme="light" storageKey="vite-ui-theme">
      {/* <PersistQueryClientProvider client={queryClient} persistOptions={{ persister: persistor }}> */}
      <QueryClientProvider client={queryClient}>
        <DrawerProvider>
          <Outlet />
          <Toaster position="top-right" expand={true} closeButton={true} />
          {/* <AssistantModal></AssistantModal> */}
          {/* <AssistantSidebar></AssistantSidebar> */}
        </DrawerProvider>
      </QueryClientProvider>
      {/* </PersistQueryClientProvider> */}
    </ThemeProvider>
  )
}

export function HydrateFallback() {
  return <div className="flex flex-col items-center justify-center h-screen">
    <p>Loading...</p>
  </div>;
}

export function ErrorBoundary({ error }: Route.ErrorBoundaryProps) {
  let message = 'Oops!'
  let details = 'An unexpected error occurred.'
  let stack: string | undefined

  if (isRouteErrorResponse(error)) {
    message = error.status === 404 ? '404' : 'Error'
    details = error.status === 404 ? 'The requested page could not be found.' : error.statusText || details
  } else if (import.meta.env.DEV && error && error instanceof Error) {
    details = error.message
    stack = error.stack
  }

  return (
    <main className="pt-16 p-4 container mx-auto">
      <h1>{message}</h1>
      <p>{details}</p>
      {stack && (
        <pre className="w-full p-4 overflow-x-auto">
          <code>{stack}</code>
        </pre>
      )}
    </main>
  )
}
