import { Link } from 'react-router'
import { ArrowRight, RefreshCw, ShieldCheck } from 'lucide-react'

import { Button, buttonVariants } from '@/components/ui/button'
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
  return (
    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">观测工作台</h1>
        <p className="mt-1 text-sm text-muted-foreground">监控智能体运行健康、调用趋势与异常处理，保障服务稳定可靠</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" className="h-10 rounded-lg bg-panel/90" onClick={onRefresh} disabled={isLoading}>
          <RefreshCw className="h-4 w-4" />
          刷新
        </Button>
        <Button asChild variant="outline" className="h-10 rounded-lg bg-panel/90">
          <Link to="/observe/audits" aria-label="打开 Audit Explorer">
            Audit Explorer
            <ShieldCheck className="h-4 w-4" />
          </Link>
        </Button>
        <Link
          to={runExplorerUrl}
          aria-label="打开 Run Explorer"
          className={cn(buttonVariants(), 'h-10 rounded-lg px-5 shadow-sm')}
        >
          打开 Run Explorer
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  )
}
