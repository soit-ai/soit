import { Link } from 'react-router'
import { ArrowRight, RefreshCw, ShieldCheck } from 'lucide-react'

import { Button, buttonVariants } from '@/components/ui/button'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'

type DashboardHeaderProps = {
  isLoading: boolean
  runExplorerUrl: string
  onRefresh: () => void
}

export function DashboardHeader({
  isLoading,
  runExplorerUrl,
  onRefresh,
}: DashboardHeaderProps) {
  const { t } = useTranslation()

  return (
    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t('observe.header.title')}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t('observe.header.description')}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" className="h-10 rounded-lg bg-panel/90" onClick={onRefresh} disabled={isLoading}>
          <RefreshCw className="h-4 w-4" />
          {t('observe.header.refresh')}
        </Button>
        <Button asChild variant="outline" className="h-10 rounded-lg bg-panel/90">
          <Link to="/observe/audits" aria-label={t('observe.header.openAuditExplorer')}>
            Audit Explorer
            <ShieldCheck className="h-4 w-4" />
          </Link>
        </Button>
        <Link
          to={runExplorerUrl}
          aria-label={t('observe.header.openRunExplorer')}
          className={cn(buttonVariants(), 'h-10 rounded-lg px-5 shadow-sm')}
        >
          {t('observe.header.openRunExplorer')}
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  )
}
