import { useState } from 'react'
import { useParams } from 'react-router'
import { toast } from 'sonner'

import { PageStatus } from '@/components/common/page-status'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useNavigate } from '@/hooks/use-navigate'
import { useQuery } from '@/hooks/use-query'
import { cancelTask, getTask, resumeTask, retryTask } from '@/services/task-service'
import { formatDateTime, isoToZonedDate } from '@/utils/date-time'

const formatTimestamp = (value?: string | null) => {
  if (!value) {
    return '-'
  }
  return formatDateTime(isoToZonedDate(value))
}

function TaskDetailPage() {
  const navigate = useNavigate()
  const { taskId = '' } = useParams()
  const [action, setAction] = useState<string | null>(null)

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['tasks', taskId],
    queryFn: () => getTask(taskId),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const task = data?.task
  // The server decides which controls are actually backed by an implementation;
  // deriving them from status alone offered a retry that never ran anything.
  const availableActions = data?.available_actions ?? []
  const canCancel = availableActions.includes('cancel')
  const canResume = availableActions.includes('resume')
  const canRetry = availableActions.includes('retry')

  const handleControl = async (action: 'cancel' | 'resume' | 'retry') => {
    try {
      setAction(action)
      if (action === 'cancel') {
        await cancelTask(taskId)
      } else if (action === 'resume') {
        await resumeTask(taskId)
      } else {
        await retryTask(taskId)
      }
      toast.success(`Task ${action} submitted`)
      await refetch()
    } catch (error) {
      console.error(`Failed to ${action} task`, error)
      toast.error(`Failed to ${action} task`)
    } finally {
      setAction(null)
    }
  }

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <Card className="border-none bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 text-white shadow-xl">
        <CardHeader className="gap-3">
          <Badge variant="secondary" className="w-fit bg-white/10 text-white hover:bg-white/10">
            Task Detail
          </Badge>
          <CardTitle className="text-3xl font-semibold tracking-tight">{isLoading ? 'Loading task...' : taskId}</CardTitle>
          <CardDescription className="text-slate-300">
            Inspect runtime status, checkpoints, and task events emitted by the new execution core.
          </CardDescription>
        </CardHeader>
      </Card>

      {isLoading && !data && (
        <PageStatus
          variant="loading"
          title="Loading task detail"
          description="Fetching runtime status, events, and checkpoints."
        />
      )}

      {!isLoading && isError && (
        <PageStatus
          variant="error"
          title="Failed to load task detail"
          description={error instanceof Error ? error.message : 'The selected task could not be loaded right now.'}
          actionLabel="Retry"
          onAction={() => refetch()}
        />
      )}

      {!isLoading && !isError && !data && (
        <PageStatus
          variant="empty"
          title="Task not found"
          description="The requested task is unavailable or no longer exists."
          actionLabel="Back to Tasks"
          onAction={() => navigate('/tasks')}
        />
      )}

      {!isLoading && !isError && data && (
        <>
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <CardTitle>Task</CardTitle>
                <div className="flex gap-2">
                  {canRetry && (
                    <Button variant="outline" size="sm" disabled={Boolean(action)} onClick={() => handleControl('retry')}>
                      Retry
                    </Button>
                  )}
                  {canResume && (
                    <Button variant="outline" size="sm" disabled={Boolean(action)} onClick={() => handleControl('resume')}>
                      Resume
                    </Button>
                  )}
                  {canCancel && (
                    <Button variant="outline" size="sm" disabled={Boolean(action)} onClick={() => handleControl('cancel')}>
                      Cancel
                    </Button>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent className="grid gap-3 text-sm md:grid-cols-2">
              <div>Status: <Badge variant="outline">{data.task.status}</Badge></div>
              <div>Type: {data.task.task_type}</div>
              <div>Agent: {data.task.agent_id || '-'}</div>
              <div>Thread: {data.task.thread_id || '-'}</div>
              <div>Created: {formatTimestamp(data.task.created_at)}</div>
              <div>Finished: {formatTimestamp(data.task.finished_at)}</div>
              <div className="md:col-span-2">Error: {data.task.error_message || '-'}</div>
            </CardContent>
          </Card>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Events</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {data.events.map((event) => (
                  <Card key={event.id}>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base">{event.event_type}</CardTitle>
                      <CardDescription>{formatTimestamp(event.created_at)}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <pre className="overflow-auto rounded-xl bg-muted p-3 text-xs">
                        {JSON.stringify(event.payload_json, null, 2)}
                      </pre>
                    </CardContent>
                  </Card>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Checkpoints</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {data.checkpoints.length === 0 && (
                  <div className="text-sm text-muted-foreground">No checkpoints recorded.</div>
                )}
                {data.checkpoints.map((checkpoint) => (
                  <Card key={checkpoint.id}>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base">Checkpoint #{checkpoint.checkpoint_no}</CardTitle>
                      <CardDescription>{checkpoint.status}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <pre className="overflow-auto rounded-xl bg-muted p-3 text-xs">
                        {JSON.stringify(checkpoint.payload_json, null, 2)}
                      </pre>
                    </CardContent>
                  </Card>
                ))}
              </CardContent>
            </Card>
          </div>
        </>
      )}

      <div className="flex justify-end">
        <Button variant="ghost" onClick={() => navigate('/tasks')}>
          Back to Tasks
        </Button>
      </div>
    </div>
  )
}

export default TaskDetailPage
