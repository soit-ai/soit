import React, { useEffect, useState } from 'react'
import { useTranslation } from '@/i18n'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import {
  ActivityIcon,
  AlertTriangleIcon,
  BarChart3Icon,
  CalendarIcon,
  ClockIcon,
  DownloadIcon,
  EyeIcon,
  FilterIcon,
  RefreshCwIcon,
  SearchIcon,
  UserIcon,
} from 'lucide-react'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useNavLayout } from '@/components/layout/nav-layout'

// Mock user behavior data
const mockUserBehaviors = [
  {
    id: 'beh-001',
    user: 'Alex Chen',
    action: 'prompt_submission',
    detailKey: 'sensitive_prompt',
    timestamp: '2025-06-01 10:30:45',
    risk: 'medium',
    model: 'GPT-4',
    ip: '192.168.1.100',
  },
  {
    id: 'beh-002',
    user: 'Jordan Lee',
    action: 'rapid_requests',
    detailKey: 'burst_requests',
    timestamp: '2025-06-01 09:15:22',
    risk: 'low',
    model: 'Claude-3',
    ip: '192.168.1.101',
  },
  {
    id: 'beh-003',
    user: 'Taylor Park',
    action: 'prompt_injection',
    detailKey: 'prompt_injection_attempt',
    timestamp: '2025-05-31 16:45:10',
    risk: 'high',
    model: 'GPT-4',
    ip: '192.168.1.102',
  },
  {
    id: 'beh-004',
    user: 'Morgan Silva',
    action: 'unusual_pattern',
    detailKey: 'unusual_usage_pattern',
    timestamp: '2025-05-31 14:20:33',
    risk: 'medium',
    model: 'Claude-3',
    ip: '192.168.1.103',
  },
  {
    id: 'beh-005',
    user: 'Alex Chen',
    action: 'sensitive_output',
    detailKey: 'sensitive_output_generated',
    timestamp: '2025-05-30 11:10:05',
    risk: 'high',
    model: 'GPT-4',
    ip: '192.168.1.100',
  },
]

// Mock abnormal user data
const mockAbnormalUsers = [
  {
    user: 'Alex Chen',
    riskScore: 85,
    abnormalActions: 12,
    lastActivity: '2025-06-01 10:30:45',
    status: 'active',
  },
  {
    user: 'Taylor Park',
    riskScore: 75,
    abnormalActions: 8,
    lastActivity: '2025-05-31 16:45:10',
    status: 'warning',
  },
  {
    user: 'Morgan Silva',
    riskScore: 60,
    abnormalActions: 5,
    lastActivity: '2025-05-31 14:20:33',
    status: 'active',
  },
]

interface UserBehaviorProps {
  subTab?: string | null
}

function BoxHeader({
  title,
  description,
  onRefresh,
  refreshLabel,
}: {
  title: string
  description: string
  onRefresh?: () => void
  refreshLabel?: string
}) {
  return (
    <div className="flex flex-1 justify-between">
      <div>
        <h3 className="text-lg font-bold">{title}</h3>
        <p className="text-sm text-muted-foreground mt-1">{description}</p>
      </div>
      {onRefresh && (
        <Button variant="outline" size="sm" onClick={onRefresh}>
          <RefreshCwIcon className="h-4 w-4 mr-2" />
          {refreshLabel}
        </Button>
      )}
    </div>
  )
}

export function UserBehavior({ subTab = null }: UserBehaviorProps) {
  const { t } = useTranslation()
  const [behaviors, setBehaviors] = useState(mockUserBehaviors)
  const [abnormalUsers, setAbnormalUsers] = useState(mockAbnormalUsers)
  const [searchQuery, setSearchQuery] = useState('')
  const [riskFilter, setRiskFilter] = useState('all')
  const [timeFilter, setTimeFilter] = useState('all')
  const { setHeaderContent } = useNavLayout()

  useEffect(() => {
    setHeaderContent(
      <BoxHeader
        title={t('safe.userBehavior.header.title')}
        description={t('safe.userBehavior.header.description')}
        refreshLabel={t('safe.userBehavior.header.refresh')}
        onRefresh={() => {
          console.log('Refreshing user behavior data...')
        }}
      />
    )
    return () => setHeaderContent(null)
  }, [setHeaderContent, t])

  const getActionLabel = (action: string) =>
    t(`safe.userBehavior.behaviors.actionLabels.${action}`, { defaultValue: action })
  const getDetailLabel = (detailKey: string) =>
    t(`safe.userBehavior.behaviors.details.${detailKey}`, { defaultValue: detailKey })

  const filteredBehaviors = behaviors.filter((behavior) => {
    const actionLabel = getActionLabel(behavior.action)
    const detailLabel = getDetailLabel(behavior.detailKey)
    const matchesSearch =
      behavior.user.toLowerCase().includes(searchQuery.toLowerCase()) ||
      detailLabel.toLowerCase().includes(searchQuery.toLowerCase()) ||
      actionLabel.toLowerCase().includes(searchQuery.toLowerCase())

    const matchesRisk = riskFilter === 'all' || behavior.risk === riskFilter

    let matchesTime = true
    if (timeFilter === 'today') {
      matchesTime = behavior.timestamp.startsWith('2025-06-01')
    } else if (timeFilter === 'yesterday') {
      matchesTime = behavior.timestamp.startsWith('2025-05-31')
    } else if (timeFilter === 'week') {
      matchesTime = behavior.timestamp.startsWith('2025-05') || behavior.timestamp.startsWith('2025-06')
    }

    return matchesSearch && matchesRisk && matchesTime
  })

  const getRiskBadge = (risk: string) => {
    switch (risk) {
      case 'high':
        return <Badge variant="destructive">{t('safe.userBehavior.behaviors.risk.high')}</Badge>
      case 'medium':
        return (
          <Badge variant="default" className="bg-amber-500">
            {t('safe.userBehavior.behaviors.risk.medium')}
          </Badge>
        )
      case 'low':
        return <Badge variant="outline">{t('safe.userBehavior.behaviors.risk.low')}</Badge>
      default:
        return <Badge variant="outline">{t('safe.userBehavior.behaviors.risk.unknown')}</Badge>
    }
  }

  const getUserStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return (
          <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
            {t('safe.userBehavior.users.status.active')}
          </Badge>
        )
      case 'warning':
        return (
          <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">
            {t('safe.userBehavior.users.status.warning')}
          </Badge>
        )
      case 'blocked':
        return (
          <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">
            {t('safe.userBehavior.users.status.blocked')}
          </Badge>
        )
      default:
        return <Badge variant="outline">{t('safe.userBehavior.users.status.unknown')}</Badge>
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">{t('safe.userBehavior.summary.highRisk.title')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div className="flex flex-col">
                <span className="text-3xl font-bold">5</span>
                <span className="text-sm text-muted-foreground">
                  {t('safe.userBehavior.summary.highRisk.caption')}
                </span>
              </div>
              <AlertTriangleIcon className="h-8 w-8 text-destructive" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">{t('safe.userBehavior.summary.abnormalUsers.title')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div className="flex flex-col">
                <span className="text-3xl font-bold">3</span>
                <span className="text-sm text-muted-foreground">
                  {t('safe.userBehavior.summary.abnormalUsers.caption')}
                </span>
              </div>
              <UserIcon className="h-8 w-8 text-amber-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">{t('safe.userBehavior.summary.analysis.title')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div className="flex flex-col">
                <span className="text-3xl font-bold">128</span>
                <span className="text-sm text-muted-foreground">
                  {t('safe.userBehavior.summary.analysis.caption')}
                </span>
              </div>
              <BarChart3Icon className="h-8 w-8 text-blue-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="behaviors" className="w-full">
        <TabsList className="mb-4">
          <TabsTrigger value="behaviors">{t('safe.userBehavior.tabs.behaviors')}</TabsTrigger>
          <TabsTrigger value="users">{t('safe.userBehavior.tabs.users')}</TabsTrigger>
          <TabsTrigger value="patterns">{t('safe.userBehavior.tabs.patterns')}</TabsTrigger>
        </TabsList>

        <TabsContent value="behaviors">
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ActivityIcon className="h-5 w-5 text-primary" />
                  <CardTitle>{t('safe.userBehavior.behaviors.title')}</CardTitle>
                </div>
                <div className="flex gap-2">
                  <Select value={riskFilter} onValueChange={setRiskFilter}>
                    <SelectTrigger className="w-[120px]">
                      <SelectValue placeholder={t('safe.userBehavior.behaviors.filters.risk.placeholder')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t('safe.userBehavior.behaviors.filters.risk.all')}</SelectItem>
                      <SelectItem value="high">{t('safe.userBehavior.behaviors.filters.risk.high')}</SelectItem>
                      <SelectItem value="medium">{t('safe.userBehavior.behaviors.filters.risk.medium')}</SelectItem>
                      <SelectItem value="low">{t('safe.userBehavior.behaviors.filters.risk.low')}</SelectItem>
                    </SelectContent>
                  </Select>

                  <Select value={timeFilter} onValueChange={setTimeFilter}>
                    <SelectTrigger className="w-[120px]">
                      <SelectValue placeholder={t('safe.userBehavior.behaviors.filters.time.placeholder')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t('safe.userBehavior.behaviors.filters.time.all')}</SelectItem>
                      <SelectItem value="today">{t('safe.userBehavior.behaviors.filters.time.today')}</SelectItem>
                      <SelectItem value="yesterday">{t('safe.userBehavior.behaviors.filters.time.yesterday')}</SelectItem>
                      <SelectItem value="week">{t('safe.userBehavior.behaviors.filters.time.week')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <CardDescription>{t('safe.userBehavior.behaviors.description')}</CardDescription>

              <div className="flex w-full items-center space-x-2 mt-4">
                <div className="relative flex-1">
                  <SearchIcon className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    type="search"
                    placeholder={t('safe.userBehavior.behaviors.searchPlaceholder')}
                    className="pl-8"
                    value={searchQuery}
                    onChange={(event) => setSearchQuery(event.target.value)}
                  />
                </div>
                <Button variant="outline" size="icon">
                  <FilterIcon className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>

            <CardContent>
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('safe.userBehavior.behaviors.table.user')}</TableHead>
                      <TableHead>{t('safe.userBehavior.behaviors.table.action')}</TableHead>
                      <TableHead>{t('safe.userBehavior.behaviors.table.details')}</TableHead>
                      <TableHead>{t('safe.userBehavior.behaviors.table.model')}</TableHead>
                      <TableHead>{t('safe.userBehavior.behaviors.table.risk')}</TableHead>
                      <TableHead>{t('safe.userBehavior.behaviors.table.time')}</TableHead>
                      <TableHead className="text-right">{t('safe.userBehavior.behaviors.table.actions')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredBehaviors.length > 0 ? (
                      filteredBehaviors.map((behavior) => (
                        <TableRow key={behavior.id}>
                          <TableCell className="font-medium">{behavior.user}</TableCell>
                          <TableCell>{getActionLabel(behavior.action)}</TableCell>
                          <TableCell className="max-w-[200px] truncate">
                            {getDetailLabel(behavior.detailKey)}
                          </TableCell>
                          <TableCell>{behavior.model}</TableCell>
                          <TableCell>{getRiskBadge(behavior.risk)}</TableCell>
                          <TableCell>{behavior.timestamp}</TableCell>
                          <TableCell className="text-right">
                            <Button variant="ghost" size="sm">
                              <EyeIcon className="h-4 w-4 mr-2" />
                              {t('safe.userBehavior.behaviors.actions.viewDetails')}
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))
                    ) : (
                      <TableRow>
                        <TableCell colSpan={7} className="h-24 text-center">
                          {t('safe.userBehavior.behaviors.empty')}
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="users">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <UserIcon className="h-5 w-5 text-primary" />
                <CardTitle>{t('safe.userBehavior.users.title')}</CardTitle>
              </div>
              <CardDescription>{t('safe.userBehavior.users.description')}</CardDescription>
            </CardHeader>

            <CardContent>
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('safe.userBehavior.users.table.user')}</TableHead>
                      <TableHead>{t('safe.userBehavior.users.table.riskScore')}</TableHead>
                      <TableHead>{t('safe.userBehavior.users.table.abnormalCount')}</TableHead>
                      <TableHead>{t('safe.userBehavior.users.table.lastActivity')}</TableHead>
                      <TableHead>{t('safe.userBehavior.users.table.status')}</TableHead>
                      <TableHead className="text-right">{t('safe.userBehavior.users.table.actions')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {abnormalUsers.map((user, index) => (
                      <TableRow key={index}>
                        <TableCell className="font-medium">{user.user}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <span
                              className={`font-medium ${
                                user.riskScore > 70
                                  ? 'text-destructive'
                                  : user.riskScore > 50
                                  ? 'text-amber-500'
                                  : 'text-muted-foreground'
                              }`}
                            >
                              {user.riskScore}
                            </span>
                            <div className="h-2 w-24 bg-muted rounded-full overflow-hidden">
                              <div
                                className={`h-full ${
                                  user.riskScore > 70
                                    ? 'bg-destructive'
                                    : user.riskScore > 50
                                    ? 'bg-amber-500'
                                    : 'bg-green-500'
                                }`}
                                style={{ width: `${user.riskScore}%` }}
                              />
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>{user.abnormalActions}</TableCell>
                        <TableCell>{user.lastActivity}</TableCell>
                        <TableCell>{getUserStatusBadge(user.status)}</TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button variant="ghost" size="sm">
                              <EyeIcon className="h-4 w-4 mr-2" />
                              {t('safe.userBehavior.users.actions.viewDetails')}
                            </Button>
                            <Button variant="outline" size="sm">
                              {t('safe.userBehavior.users.actions.restrict')}
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="patterns">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <BarChart3Icon className="h-5 w-5 text-primary" />
                <CardTitle>{t('safe.userBehavior.patterns.title')}</CardTitle>
              </div>
              <CardDescription>{t('safe.userBehavior.patterns.description')}</CardDescription>
            </CardHeader>

            <CardContent>
              <div className="flex items-center justify-center h-60 border rounded-md bg-muted/10">
                <div className="text-center">
                  <BarChart3Icon className="h-10 w-10 text-muted-foreground mx-auto mb-2" />
                  <p className="text-muted-foreground">{t('safe.userBehavior.patterns.placeholder.title')}</p>
                  <p className="text-sm text-muted-foreground">
                    {t('safe.userBehavior.patterns.placeholder.subtitle')}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
                <div className="border rounded-md p-4">
                  <h3 className="text-sm font-medium mb-2">
                    {t('safe.userBehavior.patterns.sections.frequency.title')}
                  </h3>
                  <ul className="space-y-2">
                    <li className="text-sm flex justify-between">
                      <span>{t('safe.userBehavior.patterns.sections.frequency.items.promptSubmission')}</span>
                      <span className="font-medium">65%</span>
                    </li>
                    <li className="text-sm flex justify-between">
                      <span>{t('safe.userBehavior.patterns.sections.frequency.items.rapidRequests')}</span>
                      <span className="font-medium">15%</span>
                    </li>
                    <li className="text-sm flex justify-between">
                      <span>{t('safe.userBehavior.patterns.sections.frequency.items.unusualPattern')}</span>
                      <span className="font-medium">12%</span>
                    </li>
                  </ul>
                </div>

                <div className="border rounded-md p-4">
                  <h3 className="text-sm font-medium mb-2">
                    {t('safe.userBehavior.patterns.sections.riskWindows.title')}
                  </h3>
                  <ul className="space-y-2">
                    <li className="text-sm flex justify-between">
                      <span>10:00 - 12:00</span>
                      <span className="font-medium">35%</span>
                    </li>
                    <li className="text-sm flex justify-between">
                      <span>14:00 - 16:00</span>
                      <span className="font-medium">28%</span>
                    </li>
                    <li className="text-sm flex justify-between">
                      <span>20:00 - 22:00</span>
                      <span className="font-medium">22%</span>
                    </li>
                  </ul>
                </div>

                <div className="border rounded-md p-4">
                  <h3 className="text-sm font-medium mb-2">
                    {t('safe.userBehavior.patterns.sections.modelUsage.title')}
                  </h3>
                  <ul className="space-y-2">
                    <li className="text-sm flex justify-between">
                      <span>GPT-4</span>
                      <span className="font-medium">58%</span>
                    </li>
                    <li className="text-sm flex justify-between">
                      <span>Claude-3</span>
                      <span className="font-medium">32%</span>
                    </li>
                    <li className="text-sm flex justify-between">
                      <span>{t('safe.userBehavior.patterns.sections.modelUsage.items.other')}</span>
                      <span className="font-medium">10%</span>
                    </li>
                  </ul>
                </div>
              </div>
            </CardContent>

            <CardFooter className="flex justify-end gap-2">
              <Button variant="outline">
                <CalendarIcon className="h-4 w-4 mr-2" />
                {t('safe.userBehavior.patterns.footer.selectRange')}
              </Button>
              <Button>
                <DownloadIcon className="h-4 w-4 mr-2" />
                {t('safe.userBehavior.patterns.footer.exportReport')}
              </Button>
            </CardFooter>
          </Card>
        </TabsContent>
      </Tabs>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <ClockIcon className="h-5 w-5 text-primary" />
            <CardTitle>{t('safe.userBehavior.monitoring.title')}</CardTitle>
          </div>
          <CardDescription>{t('safe.userBehavior.monitoring.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Label>{t('safe.userBehavior.monitoring.settings.enableRealtime')}</Label>
            </div>
            <Switch defaultChecked />
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Label>{t('safe.userBehavior.monitoring.settings.monitorHighRisk')}</Label>
            </div>
            <Switch defaultChecked />
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Label>{t('safe.userBehavior.monitoring.settings.monitorSensitive')}</Label>
            </div>
            <Switch defaultChecked />
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Label>{t('safe.userBehavior.monitoring.settings.abnormalAlerts')}</Label>
            </div>
            <Switch defaultChecked />
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Label>{t('safe.userBehavior.monitoring.settings.autoRestrict')}</Label>
            </div>
            <Switch />
          </div>
        </CardContent>
        <CardFooter className="flex justify-end gap-2">
          <Button variant="outline">{t('safe.userBehavior.monitoring.actions.reset')}</Button>
          <Button>{t('safe.userBehavior.monitoring.actions.save')}</Button>
        </CardFooter>
      </Card>
    </div>
  )
}
