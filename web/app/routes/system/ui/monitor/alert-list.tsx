import React from 'react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { AlertCircle, AlertTriangle, Info, CheckCircle } from 'lucide-react'

export interface Alert {
  id: string
  service: string
  severity: 'critical' | 'warning' | 'info'
  message: string
  timestamp: string
  status: 'active' | 'resolved'
}

interface AlertListProps {
  alerts: Alert[]
  formatDate?: (date: string) => string
}

export function AlertList({ alerts, formatDate }: AlertListProps) {
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

  // 获取严重程度徽章
  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'critical':
        return (
          <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">
            <AlertCircle className="mr-1 h-4 w-4" />
            严重
          </Badge>
        )
      case 'warning':
        return (
          <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">
            <AlertTriangle className="mr-1 h-4 w-4" />
            警告
          </Badge>
        )
      case 'info':
        return (
          <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
            <Info className="mr-1 h-4 w-4" />
            信息
          </Badge>
        )
      default:
        return <Badge variant="outline">{severity}</Badge>
    }
  }

  // 获取状态徽章
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return (
          <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">
            活跃
          </Badge>
        )
      case 'resolved':
        return (
          <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
            <CheckCircle className="mr-1 h-4 w-4" />
            已解决
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
          <TableHead>服务</TableHead>
          <TableHead>严重程度</TableHead>
          <TableHead>消息</TableHead>
          <TableHead>时间</TableHead>
          <TableHead>状态</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {alerts.map((alert) => (
          <TableRow key={alert.id}>
            <TableCell className="font-medium">{alert.service}</TableCell>
            <TableCell>{getSeverityBadge(alert.severity)}</TableCell>
            <TableCell>{alert.message}</TableCell>
            <TableCell>{formatDateTime(alert.timestamp)}</TableCell>
            <TableCell>{getStatusBadge(alert.status)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
