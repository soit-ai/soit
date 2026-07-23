import { Palette } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

function Page() {
  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div>
        <h3 className="text-lg font-bold tracking-tight">Appearance</h3>
        <p className="mt-1 text-sm text-muted-foreground">Community 1.0 release scope</p>
      </div>
      <Alert>
        <Palette className="h-4 w-4" />
        <AlertTitle>Theme switching is available from the application header</AlertTitle>
        <AlertDescription>
          Additional font, layout, color-scheme, animation, and border-radius preferences are not implemented in this release. This page does not simulate saving them.
        </AlertDescription>
      </Alert>
    </div>
  )
}

export default Page
