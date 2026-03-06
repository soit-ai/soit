import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from '@/i18n'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { cn } from '@/lib/utils'
import { formatDateTime, isoToZonedDate } from '@/utils/date-time'
import {
  archiveNotification,
  listNotifications,
  markNotificationRead,
  markNotificationsRead,
  type Notification,
} from '@/services/notification-service'
import { AlertTriangle, CheckCircle2, Info, RefreshCw, Bell, Archive, Filter, Search } from 'lucide-react'
import { useNavigate } from '@/hooks/use-navigate'

const PAGE_SIZE = 20
const statusOptions = [
  { value: 'all', labelKey: 'notification.filters.status.all' },
  { value: 'unread', labelKey: 'notification.filters.status.unread' },
  { value: 'read', labelKey: 'notification.filters.status.read' },
  { value: 'archived', labelKey: 'notification.filters.status.archived' },
]
const severityOptions = [
  { value: 'all', labelKey: 'notification.filters.severity.all' },
  { value: 'info', labelKey: 'notification.filters.severity.info' },
  { value: 'warning', labelKey: 'notification.filters.severity.warning' },
  { value: 'error', labelKey: 'notification.filters.severity.error' },
  { value: 'success', labelKey: 'notification.filters.severity.success' },
]

const getSeverityIcon = (severity?: string | null) => {
  switch (severity) {
    case 'warning':
      return <AlertTriangle className="h-4 w-4 text-yellow-500" />
    case 'error':
      return <AlertTriangle className="h-4 w-4 text-red-500" />
    case 'success':
      return <CheckCircle2 className="h-4 w-4 text-emerald-500" />
    default:
      return <Info className="h-4 w-4 text-blue-500" />
  }
}

const formatNotificationTime = (value?: string | null) => {
  if (!value) return ''
  return formatDateTime(isoToZonedDate(value), 'yyyy-MM-dd HH:mm')
}

export default function NotificationsPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [nextPageToken, setNextPageToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [statusFilter, setStatusFilter] = useState('all')
  const [severityFilter, setSeverityFilter] = useState('all')
  const [typeFilter, setTypeFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')

  const requestParams = useMemo(() => {
    return {
      page_size: PAGE_SIZE,
      status: statusFilter === 'all' ? undefined : statusFilter,
      severity: severityFilter === 'all' ? undefined : severityFilter,
      type: typeFilter === 'all' ? undefined : typeFilter,
      include_archived: statusFilter === 'archived',
    }
  }, [severityFilter, statusFilter, typeFilter])

  const fetchNotifications = useCallback(
    async ({ append }: { append: boolean }) => {
      if (append && !nextPageToken) return
      try {
        append ? setLoadingMore(true) : setLoading(true)
        const response = await listNotifications({
          ...requestParams,
          page_token: append ? nextPageToken || undefined : undefined,
        })
        const items = response.items || []
        setNotifications((prev) => (append ? [...prev, ...items] : items))
        setNextPageToken(response.next_page_token || null)
      } catch (error) {
        console.error('Failed to fetch notifications:', error)
        setNotifications((prev) => (prev.length ? prev : []))
        setNextPageToken(null)
      } finally {
        setLoading(false)
        setLoadingMore(false)
      }
    },
    [nextPageToken, requestParams]
  )

  useEffect(() => {
    fetchNotifications({ append: false })
  }, [fetchNotifications])

  const filteredNotifications = useMemo(() => {
    if (!searchQuery.trim()) {
      return notifications
    }
    const query = searchQuery.toLowerCase()
    return notifications.filter((item) => {
      const content = `${item.title || ''} ${item.content || ''}`.toLowerCase()
      return content.includes(query)
    })
  }, [notifications, searchQuery])

  const handleMarkAllRead = async () => {
    await markNotificationsRead({ all: true })
    setNotifications((prev) =>
      prev.map((item) => (item.status === 'unread' ? { ...item, status: 'read' } : item))
    )
  }

  const handleMarkRead = async (notification: Notification) => {
    if (notification.status === 'read') return
    await markNotificationRead(notification.id)
    setNotifications((prev) =>
      prev.map((item) => (item.id === notification.id ? { ...item, status: 'read' } : item))
    )
  }

  const handleArchive = async (notification: Notification) => {
    await archiveNotification(notification.id)
    setNotifications((prev) => prev.filter((item) => item.id !== notification.id))
  }

  const handleOpenNotification = async (notification: Notification) => {
    await handleMarkRead(notification)
    const action = notification.action || {}
    if (action.deeplink) {
      window.open(action.deeplink, '_blank', 'noopener,noreferrer')
      return
    }
    if (action.route) {
      navigate(action.route)
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'unread':
        return (
          <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
            {t('notification.item.status.unread')}
          </Badge>
        )
      case 'read':
        return (
          <Badge variant="outline" className="bg-muted text-muted-foreground border-muted">
            {t('notification.item.status.read')}
          </Badge>
        )
      case 'archived':
        return (
          <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">
            {t('notification.item.status.archived')}
          </Badge>
        )
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  const getSeverityBadge = (severity?: string | null) => {
    switch (severity) {
      case 'warning':
        return <Badge variant="warning">{t('notification.filters.severity.warning')}</Badge>
      case 'error':
        return <Badge variant="destructive">{t('notification.filters.severity.error')}</Badge>
      case 'success':
        return <Badge variant="success">{t('notification.filters.severity.success')}</Badge>
      default:
        return <Badge variant="outline">{t('notification.filters.severity.info')}</Badge>
    }
  }

  const getTypeBadge = (type?: string | null) => {
    switch (type) {
      case 'system':
        return <Badge variant="secondary">{t('notification.item.type.system')}</Badge>
      case 'message':
        return <Badge variant="default">{t('notification.item.type.message')}</Badge>
      case 'alert':
        return <Badge variant="warning">{t('notification.item.type.alert')}</Badge>
      case 'reminder':
        return <Badge variant="outline">{t('notification.item.type.reminder')}</Badge>
      case 'custom':
        return <Badge variant="outline">{t('notification.item.type.custom')}</Badge>
      default:
        return <Badge variant="outline">{type || t('notification.filters.type.all')}</Badge>
    }
  }

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Bell className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-bold">{t('notification.title')}</h2>
          </div>
          <p className="text-sm text-muted-foreground">{t('notification.description')}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => fetchNotifications({ append: false })} disabled={loading}>
            <RefreshCw className={cn('mr-2 h-4 w-4', loading && 'animate-spin')} />
            {t('notification.actions.refresh')}
          </Button>
          <Button size="sm" onClick={handleMarkAllRead}>
            {t('notification.actions.markAllRead')}
          </Button>
        </div>
      </div>

      <Tabs value={typeFilter} onValueChange={setTypeFilter} className="mt-4 w-full">
            <TabsList className="grid w-full max-w-lg grid-cols-6">
              <TabsTrigger value="all">{t('notification.filters.type.all')}</TabsTrigger>
              <TabsTrigger value="system">{t('notification.filters.type.system')}</TabsTrigger>
              <TabsTrigger value="message">{t('notification.filters.type.message')}</TabsTrigger>
              <TabsTrigger value="alert">{t('notification.filters.type.alert')}</TabsTrigger>
              <TabsTrigger value="reminder">{t('notification.filters.type.reminder')}</TabsTrigger>
              <TabsTrigger value="custom">{t('notification.filters.type.custom')}</TabsTrigger>
            </TabsList>
          </Tabs>
      <Card>
        <CardHeader>
          <CardTitle>{t('notification.list.title')}</CardTitle>
          <CardDescription>{t('notification.list.description')}</CardDescription>
          <div className="flex flex-wrap items-center justify-between gap-3 mt-4">
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" size="sm">
                <Filter className="mr-2 h-4 w-4" />
                {t('notification.filters.button')}
              </Button>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-[170px]">
                  <SelectValue placeholder={t('notification.filters.status.label')} />
                </SelectTrigger>
                <SelectContent>
                  {statusOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {t(option.labelKey)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={severityFilter} onValueChange={setSeverityFilter}>
                <SelectTrigger className="w-[170px]">
                  <SelectValue placeholder={t('notification.filters.severity.label')} />
                </SelectTrigger>
                <SelectContent>
                  {severityOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {t(option.labelKey)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                type="search"
                placeholder={t('notification.search.placeholder')}
                className="w-[250px] pl-8"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading && <div className="text-sm text-muted-foreground">{t('notification.list.loading')}</div>}
          {!loading && filteredNotifications.length === 0 && (
            <div className="text-sm text-muted-foreground">{t('notification.list.empty')}</div>
          )}
          {!loading && filteredNotifications.length > 0 && (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('notification.list.table.id')}</TableHead>
                    <TableHead>{t('notification.list.table.title')}</TableHead>
                    <TableHead>{t('notification.list.table.type')}</TableHead>
                    <TableHead>{t('notification.list.table.severity')}</TableHead>
                    <TableHead>{t('notification.list.table.status')}</TableHead>
                    <TableHead>{t('notification.list.table.createdAt')}</TableHead>
                    <TableHead>{t('notification.list.table.updatedAt')}</TableHead>
                    <TableHead className="text-right">{t('notification.list.table.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredNotifications.map((notification) => (
                    <TableRow key={notification.id}>
                      <TableCell className="text-xs text-muted-foreground">{notification.id}</TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          <button
                            type="button"
                            className={cn(
                              'text-left font-medium hover:underline',
                              notification.status === 'unread' && 'text-foreground'
                            )}
                            onClick={() => handleOpenNotification(notification)}
                          >
                            {notification.title}
                          </button>
                          {notification.content && (
                            <p className="text-xs text-muted-foreground line-clamp-2">
                              {notification.content}
                            </p>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>{getTypeBadge(notification.type)}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {getSeverityIcon(notification.severity)}
                          {getSeverityBadge(notification.severity)}
                        </div>
                      </TableCell>
                      <TableCell>{getStatusBadge(notification.status)}</TableCell>
                      <TableCell>{formatNotificationTime(notification.created_at)}</TableCell>
                      <TableCell>{formatNotificationTime(notification.updated_at)}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          {notification.status === 'unread' && (
                            <Button size="sm" variant="outline" onClick={() => handleMarkRead(notification)}>
                              {t('notification.actions.markRead')}
                            </Button>
                          )}
                          <Button size="sm" variant="ghost" onClick={() => handleArchive(notification)}>
                            <Archive className="mr-2 h-4 w-4" />
                            {t('notification.actions.archive')}
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
        <CardFooter className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-sm text-muted-foreground">
            {t('notification.list.summary', {
              filtered: filteredNotifications.length,
              total: notifications.length,
            })}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled>
              {t('notification.pagination.prev')}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => fetchNotifications({ append: true })}
              disabled={!nextPageToken || loadingMore}
            >
              {loadingMore ? t('notification.list.loadingMore') : t('notification.pagination.next')}
            </Button>
          </div>
        </CardFooter>
      </Card>
    </div>
  )
}
