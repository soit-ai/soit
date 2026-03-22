import React from 'react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { CheckCircle, AlertTriangle, XCircle } from 'lucide-react'

export interface Service {
  id: string
  name: string
  status: 'healthy' | 'warning' | 'critical'
  uptime: string
  responseTime: string
  lastChecked: string
}

interface ServiceStatusTableProps {
  services: Service[]
  formatDate?: (date: string) => string
}

export function ServiceStatusTable({ services, formatDate }: ServiceStatusTableProps) {
  // 默认日期格式化函数
  const defaultFormatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  const formatDateTime = formatDate || defaultFormatDate

  // 获取状态徽章
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'healthy':
        return (
          <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
            <CheckCircle className="mr-1 h-4 w-4" />
            正常
          </Badge>
        )
      case 'warning':
        return (
          <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">
            <AlertTriangle className="mr-1 h-4 w-4" />
            警告
          </Badge>
        )
      case 'critical':
        return (
          <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">
            <XCircle className="mr-1 h-4 w-4" />
            严重
          </Badge>
        )
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>服务名称</TableHead>
          <TableHead>状态</TableHead>
          <TableHead>可用性</TableHead>
          <TableHead>响应时间</TableHead>
          <TableHead>最后检查时间</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {services.map((service) => (
          <TableRow key={service.id}>
            <TableCell className="font-medium">{service.name}</TableCell>
            <TableCell>{getStatusBadge(service.status)}</TableCell>
            <TableCell>{service.uptime}</TableCell>
            <TableCell>{service.responseTime}</TableCell>
            <TableCell>{formatDateTime(service.lastChecked)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
