import { BarChart3 } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

function Page() {
  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div>
        <h3 className="text-lg font-bold tracking-tight">Analytics preferences</h3>
        <p className="mt-1 text-sm text-muted-foreground">Community 1.0 release scope</p>
      </div>
      <Alert>
        <BarChart3 className="h-4 w-4" />
        <AlertTitle>Preference and export APIs are unavailable</AlertTitle>
        <AlertDescription>
          Community 1.0 does not persist analytics preferences or provide an analytics export operation. Runtime observations remain available in Observe.
        </AlertDescription>
      </Alert>
    </div>
  )
}

export default Page
