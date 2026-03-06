import { TrendingUp } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'

interface StatCardProps {
  title: string
  value: string | number
  icon: React.ReactNode
  iconBgClass: string
  iconClass: string
  trend?: {
    value: string
    isPositive: boolean
    label: string
  }
}

export function StatCard({ title, value, icon, iconBgClass, iconClass, trend }: StatCardProps) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex justify-between items-center">
          <div>
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <h3 className="text-2xl font-bold mt-1">{value}</h3>
          </div>
          <div className={`h-12 w-12 rounded-full ${iconBgClass} flex items-center justify-center`}>
            {icon}
          </div>
        </div>
        {trend && (
          <div className="mt-4 flex items-center text-sm">
            <TrendingUp className={`h-4 w-4 ${trend.isPositive ? 'text-green-500' : 'text-red-500'} mr-1`} />
            <span className={trend.isPositive ? 'text-green-500 font-medium' : 'text-red-500 font-medium'}>
              {trend.value}
            </span>
            <span className="text-muted-foreground ml-1">{trend.label}</span>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
