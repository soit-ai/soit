import { DatabaseZap } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

function Page() {
  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div>
        <h3 className="text-lg font-bold tracking-tight">Privacy and data rights</h3>
        <p className="mt-1 text-sm text-muted-foreground">Community 1.0 release scope</p>
      </div>
      <Alert>
        <DatabaseZap className="h-4 w-4" />
        <AlertTitle>Self-service privacy operations are unavailable</AlertTitle>
        <AlertDescription>
          This release does not provide account data export, account deletion, cookie-consent, or analytics-preference APIs. No request is submitted from this page. Operators must use their documented administrative process.
        </AlertDescription>
      </Alert>
    </div>
  )
}

export default Page
