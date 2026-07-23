import { CreditCard } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

function Page() {
  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div>
        <h3 className="text-lg font-bold tracking-tight">Billing</h3>
        <p className="mt-1 text-sm text-muted-foreground">Community 1.0 release scope</p>
      </div>
      <Alert>
        <CreditCard className="h-4 w-4" />
        <AlertTitle>Billing is not part of SOIT Community</AlertTitle>
        <AlertDescription>
          Community 1.0 has no subscription, payment-method, invoice, or upgrade workflow. This page displays no synthetic plan or payment data.
        </AlertDescription>
      </Alert>
    </div>
  )
}

export default Page
