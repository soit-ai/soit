import React, { useState, useEffect } from 'react'
import { useTranslation } from '@/i18n'
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import {
  ClipboardListIcon,
  SearchIcon,
  FilterIcon,
  DownloadIcon,
  CalendarIcon,
  UserIcon,
  EyeIcon,
  RefreshCwIcon
} from 'lucide-react'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useNavLayout } from '@/components/layout/nav-layout'

// Mock audit log data.
const mockAuditLogs = [
  {
    id: 'log-001',
    user: 'Admin',
    action: 'login',
    resource: 'System',
    details: 'Login succeeded',
    timestamp: '2025-06-01 10:30:45',
    ip: '192.168.1.100',
    status: 'success',
  },
  {
    id: 'log-002',
    user: 'Alex Chen',
    action: 'create',
    resource: 'Security rule',
    details: 'Created a new security rule',
    timestamp: '2025-06-01 09:15:22',
    ip: '192.168.1.101',
    status: 'success',
  },
  {
    id: 'log-003',
    user: 'Taylor Li',
    action: 'update',
    resource: 'Sensitive words',
    details: 'Updated the sensitive word list',
    timestamp: '2025-05-31 16:45:10',
    ip: '192.168.1.102',
    status: 'success',
  },
  {
    id: 'log-004',
    user: 'Morgan Wu',
    action: 'delete',
    resource: 'API key',
    details: 'Deleted an API key',
    timestamp: '2025-05-31 14:20:33',
    ip: '192.168.1.103',
    status: 'success',
  },
  {
    id: 'log-005',
    user: 'Sam Zhao',
    action: 'login',
    resource: 'System',
    details: 'Login failed: invalid password',
    timestamp: '2025-05-30 11:10:05',
    ip: '192.168.1.104',
    status: 'failure',
  },
  {
    id: 'log-006',
    user: 'System',
    action: 'backup',
    resource: 'Database',
    details: 'Automated backup executed',
    timestamp: '2025-05-30 03:00:00',
    ip: '127.0.0.1',
    status: 'success',
  },
  {
    id: 'log-007',
    user: 'Admin',
    action: 'permission',
    resource: 'User permissions',
    details: 'Updated user permission settings',
    timestamp: '2025-05-29 15:45:22',
    ip: '192.168.1.100',
    status: 'success',
  },
]

interface AuditLogsProps {
  subTab?: string | null
}

function BoxHeader({ title, description, onRefresh, onExport }: {
  title: string
  description: string
  onRefresh?: () => void
  onExport?: () => void
}) {
  const { t } = useTranslation()

  return (
    <div className="flex flex-1 justify-between">
      <div>
        <h3 className="text-lg font-bold">{title}</h3>
        <p className="text-sm text-muted-foreground mt-1">{description}</p>
      </div>
      <div className="flex gap-2">
        {onRefresh && (
          <Button variant="outline" size="sm" onClick={onRefresh}>
            <RefreshCwIcon className="h-4 w-4 mr-2" />
            {t('safe.auditLogs.actions.refresh')}
          </Button>
        )}
        {onExport && (
          <Button variant="outline" size="sm" onClick={onExport}>
            <DownloadIcon className="h-4 w-4 mr-2" />
            {t('safe.auditLogs.actions.export')}
          </Button>
        )}
      </div>
    </div>
  )
}

export function AuditLogs({ subTab = null }: AuditLogsProps) {
  const { t } = useTranslation()
  const { setHeaderContent } = useNavLayout()
  const [logs, setLogs] = useState(mockAuditLogs)
  const [searchQuery, setSearchQuery] = useState('')
  const [actionFilter, setActionFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [timeFilter, setTimeFilter] = useState('all')

  // Set header content.
  useEffect(() => {
    setHeaderContent(
      <BoxHeader
        title={t('safe.auditLogs.header.title')}
        description={t('safe.auditLogs.header.description')}
        onRefresh={handleRefreshLogs}
        onExport={handleExportLogs}
      />
    )
    return () => setHeaderContent(null)
  }, [setHeaderContent, t])

  // Filter logs based on user selections.
  const filteredLogs = logs.filter(log => {
    const matchesSearch =
      log.user.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.details.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.resource.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.ip.includes(searchQuery)

    const matchesAction = actionFilter === 'all' || log.action === actionFilter
    const matchesStatus = statusFilter === 'all' || log.status === statusFilter

    // Simple time filter.
    let matchesTime = true
    if (timeFilter === 'today') {
      matchesTime = log.timestamp.startsWith('2025-06-01')
    } else if (timeFilter === 'yesterday') {
      matchesTime = log.timestamp.startsWith('2025-05-31')
    } else if (timeFilter === 'week') {
      matchesTime = log.timestamp.startsWith('2025-05') || log.timestamp.startsWith('2025-06')
    }

    return matchesSearch && matchesAction && matchesStatus && matchesTime
  })

  // Render action badge.
  const getActionDisplay = (action: string) => {
    switch (action) {
      case 'login':
        return <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">{t('safe.auditLogs.action.login')}</Badge>
      case 'create':
        return <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">{t('safe.auditLogs.action.create')}</Badge>
      case 'update':
        return <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">{t('safe.auditLogs.action.update')}</Badge>
      case 'delete':
        return <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">{t('safe.auditLogs.action.delete')}</Badge>
      case 'permission':
        return <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-200">{t('safe.auditLogs.action.permission')}</Badge>
      case 'backup':
        return <Badge variant="outline" className="bg-gray-50 text-gray-700 border-gray-200">{t('safe.auditLogs.action.backup')}</Badge>
      default:
        return <Badge variant="outline">{action}</Badge>
    }
  }

  // Render status badge.
  const getStatusDisplay = (status: string) => {
    switch (status) {
      case 'success':
        return <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">{t('safe.auditLogs.status.success')}</Badge>
      case 'failure':
        return <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">{t('safe.auditLogs.status.failure')}</Badge>
      case 'warning':
        return <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">{t('safe.auditLogs.status.warning')}</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  // Refresh logs.
  const handleRefreshLogs = () => {
    console.log('Refreshing audit logs')
  }

  // Export logs.
  const handleExportLogs = () => {
    console.log('Exporting audit logs')
  }

  // View log details.
  const handleViewLogDetails = (logId: string) => {
    console.log('View log details', logId)
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center gap-2">
            <ClipboardListIcon className="h-5 w-5 text-primary" />
            <CardTitle>{t('safe.auditLogs.card.title')}</CardTitle>
          </div>
          <CardDescription>
            {t('safe.auditLogs.card.description')}
          </CardDescription>

          <div className="flex flex-wrap gap-2 mt-4">
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <SearchIcon className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  type="search"
                  placeholder={t('safe.auditLogs.searchPlaceholder')}
                  className="pl-8"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            </div>

            <Select value={actionFilter} onValueChange={setActionFilter}>
              <SelectTrigger className="w-[120px]">
                <SelectValue placeholder={t('safe.auditLogs.filters.action.label')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('safe.auditLogs.filters.action.all')}</SelectItem>
                <SelectItem value="login">{t('safe.auditLogs.filters.action.login')}</SelectItem>
                <SelectItem value="create">{t('safe.auditLogs.filters.action.create')}</SelectItem>
                <SelectItem value="update">{t('safe.auditLogs.filters.action.update')}</SelectItem>
                <SelectItem value="delete">{t('safe.auditLogs.filters.action.delete')}</SelectItem>
                <SelectItem value="permission">{t('safe.auditLogs.filters.action.permission')}</SelectItem>
                <SelectItem value="backup">{t('safe.auditLogs.filters.action.backup')}</SelectItem>
              </SelectContent>
            </Select>

            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[120px]">
                <SelectValue placeholder={t('safe.auditLogs.filters.status.label')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('safe.auditLogs.filters.status.all')}</SelectItem>
                <SelectItem value="success">{t('safe.auditLogs.filters.status.success')}</SelectItem>
                <SelectItem value="failure">{t('safe.auditLogs.filters.status.failure')}</SelectItem>
                <SelectItem value="warning">{t('safe.auditLogs.filters.status.warning')}</SelectItem>
              </SelectContent>
            </Select>

            <Select value={timeFilter} onValueChange={setTimeFilter}>
              <SelectTrigger className="w-[120px]">
                <SelectValue placeholder={t('safe.auditLogs.filters.time.label')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('safe.auditLogs.filters.time.all')}</SelectItem>
                <SelectItem value="today">{t('safe.auditLogs.filters.time.today')}</SelectItem>
                <SelectItem value="yesterday">{t('safe.auditLogs.filters.time.yesterday')}</SelectItem>
                <SelectItem value="week">{t('safe.auditLogs.filters.time.week')}</SelectItem>
              </SelectContent>
            </Select>

            <Button variant="outline" size="icon">
              <FilterIcon className="h-4 w-4" />
            </Button>

            <Button variant="outline" size="icon">
              <CalendarIcon className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>

        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('safe.auditLogs.table.time')}</TableHead>
                  <TableHead>{t('safe.auditLogs.table.user')}</TableHead>
                  <TableHead>{t('safe.auditLogs.table.action')}</TableHead>
                  <TableHead>{t('safe.auditLogs.table.resource')}</TableHead>
                  <TableHead>{t('safe.auditLogs.table.details')}</TableHead>
                  <TableHead>{t('safe.auditLogs.table.ip')}</TableHead>
                  <TableHead>{t('safe.auditLogs.table.status')}</TableHead>
                  <TableHead className="text-right">{t('safe.auditLogs.table.operations')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredLogs.length > 0 ? (
                  filteredLogs.map((log) => (
                    <TableRow key={log.id}>
                      <TableCell className="whitespace-nowrap">{log.timestamp}</TableCell>
                      <TableCell className="whitespace-nowrap">
                        <div className="flex items-center gap-1">
                          <UserIcon className="h-3.5 w-3.5 text-muted-foreground" />
                          <span>{log.user}</span>
                        </div>
                      </TableCell>
                      <TableCell>{getActionDisplay(log.action)}</TableCell>
                      <TableCell>{log.resource}</TableCell>
                      <TableCell className="max-w-[200px] truncate">{log.details}</TableCell>
                      <TableCell className="font-mono text-xs">{log.ip}</TableCell>
                      <TableCell>{getStatusDisplay(log.status)}</TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleViewLogDetails(log.id)}
                        >
                          <EyeIcon className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={8} className="h-24 text-center">
                      {t('safe.auditLogs.empty')}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>

          <div className="flex items-center justify-between mt-4">
            <div className="text-sm text-muted-foreground">
              {t('safe.auditLogs.summary', { filtered: filteredLogs.length, total: logs.length })}
            </div>
            <div className="flex gap-1">
              <Button variant="outline" size="sm" disabled>
                {t('safe.auditLogs.pagination.prev')}
              </Button>
              <Button variant="outline" size="sm" disabled>
                {t('safe.auditLogs.pagination.next')}
              </Button>
            </div>
          </div>
        </CardContent>

        <CardFooter className="flex justify-between">
          <div className="flex gap-4 text-sm">
            <div className="flex items-center gap-1">
              <div className="h-2 w-2 rounded-full bg-green-500"></div>
              <span>{t('safe.auditLogs.counts.success', { count: logs.filter(log => log.status === 'success').length })}</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="h-2 w-2 rounded-full bg-red-500"></div>
              <span>{t('safe.auditLogs.counts.failure', { count: logs.filter(log => log.status === 'failure').length })}</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="h-2 w-2 rounded-full bg-amber-500"></div>
              <span>{t('safe.auditLogs.counts.warning', { count: logs.filter(log => log.status === 'warning').length })}</span>
            </div>
          </div>

          <Button variant="outline" size="sm">
            <DownloadIcon className="h-4 w-4 mr-2" />
            {t('safe.auditLogs.actions.exportFiltered')}
          </Button>
        </CardFooter>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t('safe.auditLogs.charts.actionDistribution')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-center h-40 border rounded-md bg-muted/10">
              <div className="text-center">
                <p className="text-muted-foreground">{t('safe.auditLogs.charts.actionChart')}</p>
                <p className="text-xs text-muted-foreground">{t('safe.auditLogs.charts.placeholderNote')}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t('safe.auditLogs.charts.userActivity')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-center h-40 border rounded-md bg-muted/10">
              <div className="text-center">
                <p className="text-muted-foreground">{t('safe.auditLogs.charts.userChart')}</p>
                <p className="text-xs text-muted-foreground">{t('safe.auditLogs.charts.placeholderNote')}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t('safe.auditLogs.charts.timeDistribution')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-center h-40 border rounded-md bg-muted/10">
              <div className="text-center">
                <p className="text-muted-foreground">{t('safe.auditLogs.charts.timeChart')}</p>
                <p className="text-xs text-muted-foreground">{t('safe.auditLogs.charts.placeholderNote')}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
