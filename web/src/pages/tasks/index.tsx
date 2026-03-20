import { useMemo, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { toast } from 'sonner'

import { PageStatus } from '@/components/common/page-status'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { useQuery } from '@/hooks/use-query'
import { useNavigate } from '@/hooks/use-navigate'
import { cancelTask, listTasks, resumeTask, retryTask, type Task } from '@/services/task-service'
import { formatDateTime, isoToZonedDate } from '@/utils/date-time'

const formatTimestamp = (value?: string | null) => {
  if (!value) {
    return '-'
  }
  return formatDateTime(isoToZonedDate(value))
}

function statusVariant(status: string) {
  switch (status) {
    case 'succeeded':
      return 'default'
    case 'failed':
      return 'destructive'
    case 'running':
    case 'preparing':
      return 'secondary'
    default:
      return 'outline'
  }
}

function TasksPage() {
  const navigate = useNavigate()
  const [status, setStatus] = useState('all')
  const [search, setSearch] = useState('')
  const [actionTaskId, setActionTaskId] = useState<string | null>(null)

  const {
    data: taskPage,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['tasks', status],
    queryFn: () =>
      listTasks({
        page_size: 100,
        status: status === 'all' ? undefined : status,
      }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const tasks = useMemo(() => {
    const items = taskPage?.items || []
    if (!search.trim()) {
      return items
    }
    const keyword = search.trim().toLowerCase()
    return items.filter((task: Task) => {
      const haystack = [
        task.id,
        task.task_type,
        task.status,
        task.agent_id || '',
        task.thread_id || '',
        task.error_message || '',
      ]
        .join(' ')
        .toLowerCase()
      return haystack.includes(keyword)
    })
  }, [taskPage?.items, search])

  const handleControl = async (task: Task, action: 'cancel' | 'resume' | 'retry') => {
    try {
      setActionTaskId(task.id)
      if (action === 'cancel') {
        await cancelTask(task.id)
      } else if (action === 'resume') {
        await resumeTask(task.id)
      } else {
        await retryTask(task.id)
      }
      toast.success(`Task ${action} submitted`)
      await refetch()
    } catch (error) {
      console.error(`Failed to ${action} task`, error)
      toast.error(`Failed to ${action} task`)
    } finally {
      setActionTaskId(null)
    }
  }

  const canCancel = (task: Task) => !['succeeded', 'failed', 'canceled', 'expired'].includes(task.status)
  const canResume = (task: Task) => ['paused', 'waiting_input', 'waiting_approval'].includes(task.status)
  const canRetry = (task: Task) => ['failed', 'canceled', 'expired'].includes(task.status)

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <Card>
        <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <CardTitle>Tasks</CardTitle>
            <CardDescription>Agent runtime tasks emitted by the new execution core.</CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="queued">Queued</SelectItem>
                <SelectItem value="preparing">Preparing</SelectItem>
                <SelectItem value="running">Running</SelectItem>
                <SelectItem value="waiting_input">Waiting input</SelectItem>
                <SelectItem value="waiting_approval">Waiting approval</SelectItem>
                <SelectItem value="succeeded">Succeeded</SelectItem>
                <SelectItem value="failed">Failed</SelectItem>
                <SelectItem value="canceled">Canceled</SelectItem>
              </SelectContent>
            </Select>
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search by id, type, agent, thread"
              className="w-[280px]"
            />
            <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <PageStatus
              variant="loading"
              title="Loading tasks"
              description="Fetching runtime tasks emitted by the execution core."
            />
          )}
          {!isLoading && isError && (
            <PageStatus
              variant="error"
              title="Failed to load tasks"
              description={error instanceof Error ? error.message : 'The task list could not be loaded right now.'}
              actionLabel="Retry"
              onAction={() => refetch()}
            />
          )}
          {!isLoading && !isError && tasks.length === 0 && (
            <PageStatus
              variant="empty"
              title="No runtime tasks recorded"
              description="Task rows appear here when ingest, workflow, or agent runtime operations emit async work."
            />
          )}
          {!isLoading && !isError && tasks.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Task</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Agent</TableHead>
                  <TableHead>Thread</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Finished</TableHead>
                  <TableHead>Error</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tasks.map((task: Task) => (
                  <TableRow key={task.id}>
                    <TableCell className="font-medium">{task.id}</TableCell>
                    <TableCell>{task.task_type}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(task.status)}>{task.status}</Badge>
                    </TableCell>
                    <TableCell>{task.agent_id || '-'}</TableCell>
                    <TableCell>{task.thread_id || '-'}</TableCell>
                    <TableCell>{formatTimestamp(task.created_at)}</TableCell>
                    <TableCell>{formatTimestamp(task.finished_at)}</TableCell>
                    <TableCell className="max-w-[280px] truncate">{task.error_message || '-'}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        {canRetry(task) && (
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={actionTaskId === task.id}
                            onClick={() => handleControl(task, 'retry')}
                          >
                            Retry
                          </Button>
                        )}
                        {canResume(task) && (
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={actionTaskId === task.id}
                            onClick={() => handleControl(task, 'resume')}
                          >
                            Resume
                          </Button>
                        )}
                        {canCancel(task) && (
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={actionTaskId === task.id}
                            onClick={() => handleControl(task, 'cancel')}
                          >
                            Cancel
                          </Button>
                        )}
                        <Button variant="ghost" size="sm" onClick={() => navigate(`/tasks/${task.id}`)}>
                          View
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export default TasksPage
