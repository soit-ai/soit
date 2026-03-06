import React, { useState, useEffect } from 'react'
import { useTranslation } from '@/i18n'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import {
  AlertTriangleIcon,
  ShieldAlertIcon,
  ClockIcon,
  UserIcon,
  CheckCircleIcon,
  XCircleIcon,
  EyeIcon,
  RefreshCwIcon,
  DownloadIcon
} from 'lucide-react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table'
import { useNavLayout } from '@/components/layout/nav-layout'

// Mock security events.
const mockSecurityEvents: SecurityEvent[] = [
  {
    id: 'evt-001',
    type: 'harmful_content',
    severity: 'high',
    timestamp: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
    description: 'Detected harmful content generation attempt',
    details: 'User attempted to generate unsafe content',
    status: 'pending',
    user: 'Alex Chen',
    model: 'GPT-4',
  },
  {
    id: 'evt-002',
    type: 'pii_leak',
    severity: 'high',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
    description: 'Potential PII leakage detected',
    details: 'Model output contains suspected ID numbers',
    status: 'resolved',
    user: 'Taylor Li',
    model: 'Claude-3',
  },
  {
    id: 'evt-003',
    type: 'prompt_injection',
    severity: 'medium',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 5).toISOString(),
    description: 'Prompt injection attempt detected',
    details: 'User attempted to bypass safety constraints',
    status: 'pending',
    user: 'Morgan Wu',
    model: 'GPT-4',
  },
  {
    id: 'evt-004',
    type: 'sensitive_topic',
    severity: 'low',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 8).toISOString(),
    description: 'Sensitive topic discussion',
    details: 'Conversation involves sensitive topics',
    status: 'pending',
    user: 'Sam Zhao',
    model: 'Claude-3',
  },
  {
    id: 'evt-005',
    type: 'rate_limit',
    severity: 'low',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
    description: 'Rate limit triggered',
    details: 'User sent too many requests in a short time',
    status: 'resolved',
    user: 'Alex Chen',
    model: 'GPT-4',
  },
]

// Security event type.
interface SecurityEvent {
  id: string
  type: 'harmful_content' | 'pii_leak' | 'prompt_injection' | 'sensitive_topic' | 'rate_limit'
  severity: 'high' | 'medium' | 'low'
  timestamp: string
  description: string
  details: string
  status: 'pending' | 'resolved'
  user: string
  model: string
}

interface SecurityEventItemProps {
  event: SecurityEvent
  onViewDetails: (event: SecurityEvent) => void
}

const SecurityEventItem = ({ event, onViewDetails }: SecurityEventItemProps) => {
  const { t, i18n } = useTranslation()

  // Resolve event icon by type.
  const getEventIcon = (type: SecurityEvent['type']) => {
    switch (type) {
      case 'harmful_content':
        return <ShieldAlertIcon className="h-5 w-5 text-destructive" />
      case 'pii_leak':
        return <EyeIcon className="h-5 w-5 text-destructive" />
      case 'prompt_injection':
        return <AlertTriangleIcon className="h-5 w-5 text-amber-500" />
      case 'sensitive_topic':
        return <AlertTriangleIcon className="h-5 w-5 text-amber-500" />
      case 'rate_limit':
        return <ClockIcon className="h-5 w-5 text-muted-foreground" />
      default:
        return <AlertTriangleIcon className="h-5 w-5" />
    }
  }

  // Resolve severity badge.
  const getSeverityBadge = (severity: SecurityEvent['severity']) => {
    switch (severity) {
      case 'high':
        return <Badge variant="destructive">{t('safe.securityAlerts.severity.high')}</Badge>
      case 'medium':
        return <Badge variant="default" className="bg-amber-500">{t('safe.securityAlerts.severity.medium')}</Badge>
      case 'low':
        return <Badge variant="outline">{t('safe.securityAlerts.severity.low')}</Badge>
      default:
        return <Badge variant="outline">{t('safe.securityAlerts.severity.unknown')}</Badge>
    }
  }

  // Resolve status icon.
  const getStatusIcon = (status: SecurityEvent['status']) => {
    switch (status) {
      case 'resolved':
        return <CheckCircleIcon className="h-4 w-4 text-green-500" />
      case 'pending':
        return <XCircleIcon className="h-4 w-4 text-amber-500" />
      default:
        return null
    }
  }

  // Format timestamp.
  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleString(i18n.language, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <TableRow>
      <TableCell className="w-[50px]">{getEventIcon(event.type)}</TableCell>
      <TableCell className="font-medium">{event.description}</TableCell>
      <TableCell>{getSeverityBadge(event.severity)}</TableCell>
      <TableCell>
        <div className="flex items-center gap-1">
          {getStatusIcon(event.status)}
          <span>{event.status === 'resolved' ? t('safe.securityAlerts.status.resolved') : t('safe.securityAlerts.status.pending')}</span>
        </div>
      </TableCell>
      <TableCell>{event.user}</TableCell>
      <TableCell>{formatTime(event.timestamp)}</TableCell>
      <TableCell>
        <Button variant="ghost" size="sm" onClick={() => onViewDetails(event)}>
          {t('safe.securityAlerts.actions.viewDetails')}
        </Button>
      </TableCell>
    </TableRow>
  )
}

interface SecurityAlertsProps {
  subTab?: string | null
}

function BoxHeader({ title, description, onRefresh }: { title: string; description: string; onRefresh?: () => void }) {
  const { t } = useTranslation()

  return (
    <div className="flex flex-1 justify-between">
      <div>
        <h3 className="text-lg font-bold">{title}</h3>
        <p className="text-sm text-muted-foreground mt-1">{description}</p>
      </div>
      <div className="flex gap-2">
        <Button variant="outline" size="sm">
          <DownloadIcon className="h-4 w-4 mr-2" />
          {t('safe.securityAlerts.actions.exportReport')}
        </Button>
        {onRefresh && (
          <Button variant="outline" size="sm" onClick={onRefresh}>
            <RefreshCwIcon className="h-4 w-4 mr-2" />
            {t('safe.securityAlerts.actions.refresh')}
          </Button>
        )}
      </div>
    </div>
  )
}

export function SecurityAlerts({ subTab = null }: SecurityAlertsProps) {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState('all')
  const [selectedEvent, setSelectedEvent] = useState<SecurityEvent | null>(null)
  const { setHeaderContent } = useNavLayout()

  // Set header content.
  useEffect(() => {
    setHeaderContent(
      <BoxHeader
        title={t('safe.securityAlerts.header.title')}
        description={t('safe.securityAlerts.header.description')}
        onRefresh={() => {
          console.log('Refreshing security alerts...')
        }}
      />
    )
    return () => setHeaderContent(null)
  }, [setHeaderContent, t])

  // Filter events by tab.
  const filteredEvents = mockSecurityEvents.filter(event => {
    if (activeTab === 'all') return true
    if (activeTab === 'high') return event.severity === 'high'
    if (activeTab === 'pending') return event.status === 'pending'
    if (activeTab === 'resolved') return event.status === 'resolved'
    return true
  })

  // Handle details view.
  const handleViewDetails = (event: SecurityEvent) => {
    setSelectedEvent(event)
    console.log('View security event details:', event)
  }

  return (
    <div className="space-y-4">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="mb-4">
          <TabsTrigger value="all">{t('safe.securityAlerts.tabs.all')}</TabsTrigger>
          <TabsTrigger value="high">{t('safe.securityAlerts.tabs.high')}</TabsTrigger>
          <TabsTrigger value="pending">{t('safe.securityAlerts.tabs.pending')}</TabsTrigger>
          <TabsTrigger value="resolved">{t('safe.securityAlerts.tabs.resolved')}</TabsTrigger>
        </TabsList>

        <TabsContent value={activeTab}>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[50px]"></TableHead>
                  <TableHead>{t('safe.securityAlerts.table.description')}</TableHead>
                  <TableHead>{t('safe.securityAlerts.table.severity')}</TableHead>
                  <TableHead>{t('safe.securityAlerts.table.status')}</TableHead>
                  <TableHead>{t('safe.securityAlerts.table.user')}</TableHead>
                  <TableHead>{t('safe.securityAlerts.table.time')}</TableHead>
                  <TableHead className="text-right">{t('safe.securityAlerts.table.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredEvents.length > 0 ? (
                  filteredEvents.map((event) => (
                    <SecurityEventItem
                      key={event.id}
                      event={event}
                      onViewDetails={handleViewDetails}
                    />
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={7} className="h-24 text-center">
                      {t('safe.securityAlerts.empty')}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </TabsContent>
      </Tabs>

      <Card>
        <CardHeader>
          <CardTitle>{t('safe.securityAlerts.summary.title')}</CardTitle>
          <CardDescription>
            {t('safe.securityAlerts.summary.description')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="flex items-center p-4 border rounded-lg">
              <ShieldAlertIcon className="h-8 w-8 text-destructive mr-4" />
              <div>
                <p className="text-sm font-medium text-muted-foreground">{t('safe.securityAlerts.summary.highRisk')}</p>
                <h3 className="text-2xl font-bold">12</h3>
              </div>
            </div>

            <div className="flex items-center p-4 border rounded-lg">
              <XCircleIcon className="h-8 w-8 text-amber-500 mr-4" />
              <div>
                <p className="text-sm font-medium text-muted-foreground">{t('safe.securityAlerts.summary.pending')}</p>
                <h3 className="text-2xl font-bold">8</h3>
              </div>
            </div>

            <div className="flex items-center p-4 border rounded-lg">
              <UserIcon className="h-8 w-8 text-blue-500 mr-4" />
              <div>
                <p className="text-sm font-medium text-muted-foreground">{t('safe.securityAlerts.summary.affectedUsers')}</p>
                <h3 className="text-2xl font-bold">5</h3>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
