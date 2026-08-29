import { ExternalLink, Info } from 'lucide-react'
import { cn } from '@/lib/utils'

import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Link } from '@/components/ui/link'

function Page() {
  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div>
        <h3 className="text-lg font-bold tracking-tight">About SOIT Community</h3>
        <p className="mt-1 text-sm text-muted-foreground">Governed agent runtime and governance platform</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Info className="h-5 w-5" />Community build</CardTitle>
          <CardDescription>
            Build, execute, observe, and govern enterprise AI systems. Release identity is supplied by the published artifact and is not synthesized by this page.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          <a href="https://github.com/soit-ai/soit" target="_blank" rel="noreferrer" className={cn(buttonVariants({ variant: 'outline' }))}>
            Source <ExternalLink className="h-4 w-4" />
          </a>
          <a href="https://docs.soit.ai" target="_blank" rel="noreferrer" className={cn(buttonVariants({ variant: 'outline' }))}>
            Documentation <ExternalLink className="h-4 w-4" />
          </a>
          <Link to="/feedback" className={cn(buttonVariants())}>Send feedback</Link>
        </CardContent>
      </Card>
    </div>
  )
}

export default Page
