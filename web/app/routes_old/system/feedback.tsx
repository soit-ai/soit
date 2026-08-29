import { useCallback, useEffect, useState } from 'react'
import { BarChart3, Inbox, MessageSquarePlus, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { useTranslation } from '@/i18n'
import type { TFunction } from '@/i18n/types'
import {
  createFeedback,
  getFeedbackSummary,
  listFeedback,
  updateFeedback,
  type FeedbackCategory,
  type FeedbackPriority,
  type FeedbackStatus,
  type FeedbackSummary,
  type ProductFeedback,
} from '@/services/feedback-service'
import { useUserStore } from '@/stores/user'

type FeedbackTab = 'submit' | 'mine' | 'workspace' | 'stats'

const STATUS_OPTIONS: FeedbackStatus[] = ['open', 'in_progress', 'resolved', 'closed']
const CATEGORY_OPTIONS: FeedbackCategory[] = ['bug', 'feature', 'performance', 'usability', 'other']
const PRIORITY_OPTIONS: FeedbackPriority[] = ['low', 'medium', 'high', 'critical']

const statusBadgeVariant = (status: FeedbackStatus) => {
  if (status === 'resolved') return 'success' as const
  if (status === 'closed') return 'secondary' as const
  if (status === 'in_progress') return 'warning' as const
  return 'outline' as const
}

const priorityBadgeVariant = (priority: FeedbackPriority) => {
  if (priority === 'critical' || priority === 'high') return 'destructive' as const
  if (priority === 'medium') return 'warning' as const
  return 'secondary' as const
}

function FeedbackTable({
  items,
  loading,
  canManage,
  onManage,
}: {
  items: ProductFeedback[]
  loading: boolean
  canManage: boolean
  onManage: (item: ProductFeedback) => void
}) {
  const { t, i18n } = useTranslation()
  const formatTimestamp = (value: string) =>
    new Intl.DateTimeFormat(i18n.language, {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(value))

  if (loading) {
    return <div className="py-12 text-center text-sm text-muted-foreground">{t('system.feedback.list.loading')}</div>
  }

  if (!items.length) {
    return (
      <div className="flex flex-col items-center gap-2 py-12 text-center">
        <Inbox className="size-8 text-muted-foreground" />
        <p className="font-medium">{t('system.feedback.list.emptyTitle')}</p>
        <p className="text-sm text-muted-foreground">{t('system.feedback.list.emptyDescription')}</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <Table className="min-w-[860px]">
        <TableHeader>
          <TableRow>
            <TableHead>{t('system.feedback.list.columns.ticket')}</TableHead>
            <TableHead>{t('system.feedback.list.columns.category')}</TableHead>
            <TableHead>{t('system.feedback.list.columns.priority')}</TableHead>
            <TableHead>{t('system.feedback.list.columns.status')}</TableHead>
            <TableHead>{t('system.feedback.list.columns.created')}</TableHead>
            {canManage && <TableHead className="text-right">{t('system.feedback.list.columns.actions')}</TableHead>}
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => (
            <TableRow key={item.id}>
              <TableCell className="max-w-[360px]">
                <div className="space-y-1">
                  <p className="truncate font-medium">{item.title}</p>
                  <p className="line-clamp-2 text-xs text-muted-foreground">{item.description}</p>
                  <p className="font-mono text-[11px] text-muted-foreground">{item.id}</p>
                </div>
              </TableCell>
              <TableCell>
                <Badge variant="outline">{t(`system.feedback.category.${item.category}`)}</Badge>
              </TableCell>
              <TableCell>
                <Badge variant={priorityBadgeVariant(item.priority)}>
                  {t(`system.feedback.priority.${item.priority}`)}
                </Badge>
              </TableCell>
              <TableCell>
                <Badge variant={statusBadgeVariant(item.status)}>{t(`system.feedback.status.${item.status}`)}</Badge>
              </TableCell>
              <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                {formatTimestamp(item.created_at)}
              </TableCell>
              {canManage && (
                <TableCell className="text-right">
                  <Button
                    variant="outline"
                    size="sm"
                    aria-label={t('system.feedback.queue.manageAria', { title: item.title })}
                    onClick={() => onManage(item)}
                  >
                    {t('system.feedback.queue.manage')}
                  </Button>
                </TableCell>
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function SummaryGroup({
  title,
  values,
  label,
}: {
  title: string
  values: Record<string, number>
  label: (key: string) => string
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {Object.entries(values).map(([key, value]) => (
          <div key={key} className="flex items-center justify-between gap-4 text-sm">
            <span className="text-muted-foreground">{label(key)}</span>
            <span className="font-semibold tabular-nums">{value}</span>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

export default function FeedbackPage() {
  const { t } = useTranslation()
  const currentUser = useUserStore((state) => state.currentUser)
  const isOwner = currentUser?.workspace_role?.toLowerCase() === 'owner'
  const [activeTab, setActiveTab] = useState<FeedbackTab>('submit')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState<FeedbackCategory>('bug')
  const [priority, setPriority] = useState<FeedbackPriority>('medium')
  const [submitting, setSubmitting] = useState(false)
  const [items, setItems] = useState<ProductFeedback[]>([])
  const [loadingItems, setLoadingItems] = useState(false)
  const [summary, setSummary] = useState<FeedbackSummary | null>(null)
  const [loadingSummary, setLoadingSummary] = useState(false)
  const [selectedFeedback, setSelectedFeedback] = useState<ProductFeedback | null>(null)
  const [editStatus, setEditStatus] = useState<FeedbackStatus>('open')
  const [editPriority, setEditPriority] = useState<FeedbackPriority>('medium')
  const [resolutionNote, setResolutionNote] = useState('')
  const [savingUpdate, setSavingUpdate] = useState(false)

  const loadItems = useCallback(async (scope: 'mine' | 'workspace') => {
    try {
      setLoadingItems(true)
      const response = await listFeedback({ scope, page_size: 50 })
      setItems(response.items || [])
    } catch (error) {
      console.error('Failed to load product feedback:', error)
      setItems([])
      toast.error(t('system.feedback.toast.loadFailed'))
    } finally {
      setLoadingItems(false)
    }
  }, [t])

  const loadSummary = useCallback(async () => {
    try {
      setLoadingSummary(true)
      setSummary(await getFeedbackSummary('workspace'))
    } catch (error) {
      console.error('Failed to load feedback summary:', error)
      setSummary(null)
      toast.error(t('system.feedback.toast.loadFailed'))
    } finally {
      setLoadingSummary(false)
    }
  }, [t])

  useEffect(() => {
    if (!isOwner && (activeTab === 'workspace' || activeTab === 'stats')) {
      setActiveTab('submit')
      return
    }
    if (activeTab === 'mine') {
      void loadItems('mine')
    } else if (activeTab === 'workspace' && isOwner) {
      void loadItems('workspace')
    } else if (activeTab === 'stats' && isOwner) {
      void loadSummary()
    }
  }, [activeTab, isOwner, loadItems, loadSummary])

  const handleSubmit = async () => {
    if (!title.trim() || !description.trim()) {
      toast.error(t('system.feedback.toast.required'))
      return
    }
    try {
      setSubmitting(true)
      await createFeedback({
        title: title.trim(),
        description: description.trim(),
        category,
        priority,
        context: {
          page_path: window.location.pathname,
          browser: navigator.userAgent.slice(0, 128),
          os: navigator.platform.slice(0, 128),
        },
      })
      setTitle('')
      setDescription('')
      setCategory('bug')
      setPriority('medium')
      toast.success(t('system.feedback.toast.submitted'))
    } catch (error) {
      console.error('Failed to submit product feedback:', error)
      toast.error(t('system.feedback.toast.submitFailed'))
    } finally {
      setSubmitting(false)
    }
  }

  const openManager = (feedback: ProductFeedback) => {
    setSelectedFeedback(feedback)
    setEditStatus(feedback.status)
    setEditPriority(feedback.priority)
    setResolutionNote(feedback.resolution_note || '')
  }

  const handleUpdate = async () => {
    if (!selectedFeedback) return
    const requiresResolution = editStatus === 'resolved' || editStatus === 'closed'
    if (requiresResolution && !resolutionNote.trim()) {
      toast.error(t('system.feedback.toast.resolutionRequired'))
      return
    }
    try {
      setSavingUpdate(true)
      const updated = await updateFeedback(selectedFeedback.id, {
        status: editStatus,
        priority: editPriority,
        ...(requiresResolution ? { resolution_note: resolutionNote.trim() } : {}),
      })
      setItems((current) => current.map((item) => (item.id === updated.id ? updated : item)))
      setSelectedFeedback(null)
      toast.success(t('system.feedback.toast.updated'))
    } catch (error) {
      console.error('Failed to update product feedback:', error)
      toast.error(t('system.feedback.toast.updateFailed'))
    } finally {
      setSavingUpdate(false)
    }
  }

  return (
    <div className="flex flex-1 flex-col gap-6 p-4 sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <MessageSquarePlus className="size-5 text-primary" />
            <h1 className="text-xl font-bold tracking-tight">{t('system.feedback.title')}</h1>
          </div>
          <p className="max-w-2xl text-sm text-muted-foreground">{t('system.feedback.description')}</p>
        </div>
        {(activeTab === 'mine' || activeTab === 'workspace') && (
          <Button
            variant="outline"
            size="sm"
            disabled={loadingItems}
            onClick={() => void loadItems(activeTab === 'workspace' ? 'workspace' : 'mine')}
          >
            <RefreshCw className={`mr-2 size-4 ${loadingItems ? 'animate-spin' : ''}`} />
            {t('system.feedback.actions.refresh')}
          </Button>
        )}
      </div>

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as FeedbackTab)}>
        <TabsList className={`grid w-full max-w-2xl ${isOwner ? 'grid-cols-4' : 'grid-cols-2'}`}>
          <TabsTrigger value="submit">{t('system.feedback.tabs.submit')}</TabsTrigger>
          <TabsTrigger value="mine">{t('system.feedback.tabs.mine')}</TabsTrigger>
          {isOwner && <TabsTrigger value="workspace">{t('system.feedback.tabs.workspace')}</TabsTrigger>}
          {isOwner && <TabsTrigger value="stats">{t('system.feedback.tabs.stats')}</TabsTrigger>}
        </TabsList>

        <TabsContent value="submit" className="mt-6">
          <Card className="max-w-4xl">
            <CardHeader>
              <CardTitle>{t('system.feedback.form.title')}</CardTitle>
              <CardDescription>{t('system.feedback.form.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="feedback-title">{t('system.feedback.form.fields.title')}</Label>
                <Input
                  id="feedback-title"
                  value={title}
                  maxLength={200}
                  placeholder={t('system.feedback.form.placeholders.title')}
                  onChange={(event) => setTitle(event.target.value)}
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="feedback-category">{t('system.feedback.form.fields.category')}</Label>
                  <Select value={category} onValueChange={(value) => setCategory(value as FeedbackCategory)}>
                    <SelectTrigger id="feedback-category">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {CATEGORY_OPTIONS.map((value) => (
                        <SelectItem key={value} value={value}>{t(`system.feedback.category.${value}`)}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="feedback-priority">{t('system.feedback.form.fields.priority')}</Label>
                  <Select value={priority} onValueChange={(value) => setPriority(value as FeedbackPriority)}>
                    <SelectTrigger id="feedback-priority">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PRIORITY_OPTIONS.map((value) => (
                        <SelectItem key={value} value={value}>{t(`system.feedback.priority.${value}`)}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="feedback-description">{t('system.feedback.form.fields.description')}</Label>
                <Textarea
                  id="feedback-description"
                  value={description}
                  maxLength={5000}
                  rows={8}
                  placeholder={t('system.feedback.form.placeholders.description')}
                  onChange={(event) => setDescription(event.target.value)}
                />
              </div>
              <div className="flex justify-end">
                <Button onClick={() => void handleSubmit()} disabled={submitting}>
                  {submitting ? t('system.feedback.actions.submitting') : t('system.feedback.actions.submit')}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="mine" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>{t('system.feedback.mine.title')}</CardTitle>
              <CardDescription>{t('system.feedback.mine.description')}</CardDescription>
            </CardHeader>
            <CardContent>
              <FeedbackTable items={items} loading={loadingItems} canManage={false} onManage={openManager} />
            </CardContent>
          </Card>
        </TabsContent>

        {isOwner && (
          <TabsContent value="workspace" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>{t('system.feedback.queue.title')}</CardTitle>
                <CardDescription>{t('system.feedback.queue.description')}</CardDescription>
              </CardHeader>
              <CardContent>
                <FeedbackTable items={items} loading={loadingItems} canManage onManage={openManager} />
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {isOwner && (
          <TabsContent value="stats" className="mt-6">
            {loadingSummary ? (
              <div className="py-12 text-center text-sm text-muted-foreground">{t('system.feedback.stats.loading')}</div>
            ) : summary ? (
              <div className="space-y-4">
                <Card>
                  <CardContent className="flex items-center gap-4 p-6">
                    <div className="rounded-lg bg-primary/10 p-3"><BarChart3 className="size-5 text-primary" /></div>
                    <div>
                      <p className="text-sm text-muted-foreground">{t('system.feedback.stats.total')}</p>
                      <p className="text-3xl font-bold tabular-nums">{summary.total}</p>
                    </div>
                  </CardContent>
                </Card>
                <div className="grid gap-4 md:grid-cols-3">
                  <SummaryGroup
                    title={t('system.feedback.stats.byStatus')}
                    values={summary.by_status}
                    label={(key) => t(`system.feedback.status.${key}` as Parameters<TFunction>[0])}
                  />
                  <SummaryGroup
                    title={t('system.feedback.stats.byCategory')}
                    values={summary.by_category}
                    label={(key) => t(`system.feedback.category.${key}` as Parameters<TFunction>[0])}
                  />
                  <SummaryGroup
                    title={t('system.feedback.stats.byPriority')}
                    values={summary.by_priority}
                    label={(key) => t(`system.feedback.priority.${key}` as Parameters<TFunction>[0])}
                  />
                </div>
              </div>
            ) : (
              <div className="py-12 text-center text-sm text-muted-foreground">{t('system.feedback.stats.empty')}</div>
            )}
          </TabsContent>
        )}
      </Tabs>

      <Dialog open={Boolean(selectedFeedback)} onOpenChange={(open) => !open && setSelectedFeedback(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('system.feedback.queue.dialogTitle')}</DialogTitle>
            <DialogDescription>{selectedFeedback?.title}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="feedback-edit-status">{t('system.feedback.queue.status')}</Label>
              <Select value={editStatus} onValueChange={(value) => setEditStatus(value as FeedbackStatus)}>
                <SelectTrigger id="feedback-edit-status"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map((value) => (
                    <SelectItem key={value} value={value}>{t(`system.feedback.status.${value}`)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="feedback-edit-priority">{t('system.feedback.queue.priority')}</Label>
              <Select value={editPriority} onValueChange={(value) => setEditPriority(value as FeedbackPriority)}>
                <SelectTrigger id="feedback-edit-priority"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {PRIORITY_OPTIONS.map((value) => (
                    <SelectItem key={value} value={value}>{t(`system.feedback.priority.${value}`)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="feedback-resolution-note">{t('system.feedback.queue.resolutionNote')}</Label>
              <Textarea
                id="feedback-resolution-note"
                value={resolutionNote}
                maxLength={2000}
                rows={5}
                placeholder={t('system.feedback.queue.resolutionPlaceholder')}
                onChange={(event) => setResolutionNote(event.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedFeedback(null)}>{t('system.feedback.actions.cancel')}</Button>
            <Button onClick={() => void handleUpdate()} disabled={savingUpdate}>
              {savingUpdate ? t('system.feedback.actions.saving') : t('system.feedback.actions.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
