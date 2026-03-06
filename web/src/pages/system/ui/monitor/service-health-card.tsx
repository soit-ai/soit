import React from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { CheckCircle, AlertTriangle, XCircle } from 'lucide-react'

export interface ServiceHealthProps {
  status: 'healthy' | 'warning' | 'critical'
  name: string
  value: string
  icon?: React.ReactNode
  description?: string
}

export function ServiceHealthCard({
  status,
  name,
  value,
  icon,
  description
}: ServiceHealthProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{name}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="flex items-center space-x-2">
          <div className="text-2xl font-bold">{value}</div>
          {status === 'healthy' && (
            <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
              <CheckCircle className="mr-1 h-3 w-3" />
              正常
            </Badge>
          )}
          {status === 'warning' && (
            <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">
              <AlertTriangle className="mr-1 h-3 w-3" />
              警告
            </Badge>
          )}
          {status === 'critical' && (
            <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">
              <XCircle className="mr-1 h-3 w-3" />
              严重
            </Badge>
          )}
        </div>
        {description && <p className="text-xs text-muted-foreground mt-2">{description}</p>}
      </CardContent>
    </Card>
  )
}
