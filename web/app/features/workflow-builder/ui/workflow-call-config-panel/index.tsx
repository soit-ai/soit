import { useMemo, useRef, useState } from 'react'
import { Copy, Play, Radio, RotateCcw, Send, Square } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { useTranslation } from '@/i18n'
import {
  executeWorkflow,
  streamWorkflowExecution,
} from '@/services/workflow-service'
import { API_BASE_URL } from '@/utils/request'

type PlaygroundMode = 'http' | 'sse'

type StreamEvent = {
  event: string
  data: unknown
}

interface WorkflowCallConfigPanelProps {
  workflowId: string
  workflowName: string
  visible: boolean
  onClose: () => void
}

const DEFAULT_INPUTS = JSON.stringify({ input: 'Hello from SOIT' }, null, 2)

const toAbsoluteUrl = (path: string) => {
  if (path.startsWith('http')) return path
  return `${window.location.origin}${path}`
}

const parseEventData = (data: string): unknown => {
  try {
    return JSON.parse(data)
  } catch {
    return data
  }
}

export default function WorkflowCallConfigPanel({
  workflowId,
  workflowName,
  visible,
  onClose,
}: WorkflowCallConfigPanelProps) {
  const { t } = useTranslation()
  const [mode, setMode] = useState<PlaygroundMode>('http')
  const [inputsText, setInputsText] = useState(DEFAULT_INPUTS)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [httpResult, setHttpResult] = useState<unknown>(null)
  const [streamEvents, setStreamEvents] = useState<StreamEvent[]>([])
  const abortController = useRef<AbortController | null>(null)

  const executeEndpoint = toAbsoluteUrl(`${API_BASE_URL}/workflows/${workflowId}/execute`)
  const streamEndpoint = toAbsoluteUrl(`${API_BASE_URL}/workflows/${workflowId}/stream`)
  const endpoint = mode === 'http' ? executeEndpoint : streamEndpoint

  const parseInputs = (): Record<string, unknown> | null => {
    try {
      const value = JSON.parse(inputsText)
      if (!value || typeof value !== 'object' || Array.isArray(value)) {
        setError(t('workflow.detail.callConfig.playground.errors.objectRequired'))
        return null
      }
      return value as Record<string, unknown>
    } catch {
      setError(t('workflow.detail.callConfig.playground.errors.invalidJson'))
      return null
    }
  }

  const sample = useMemo(() => {
    let formattedInputs = inputsText
    try {
      formattedInputs = JSON.stringify(JSON.parse(inputsText))
    } catch {
      formattedInputs = '{}'
    }
    const body = mode === 'http'
      ? formattedInputs
      : JSON.stringify({ inputs: JSON.parse(formattedInputs) })
    return [
      `curl ${mode === 'sse' ? '-N ' : ''}-X POST '${endpoint}' \\`,
      "  -H 'Content-Type: application/json' \\",
      "  -H 'Authorization: Bearer YOUR_API_TOKEN' \\",
      `  --data '${body}'`,
    ].join('\n')
  }, [endpoint, inputsText, mode])

  const handleHttpRequest = async () => {
    const inputs = parseInputs()
    if (!inputs) return
    setRunning(true)
    setError(null)
    setHttpResult(null)
    try {
      const started = performance.now()
      const response = await executeWorkflow(workflowId, inputs)
      setHttpResult({
        duration_ms: Math.round((performance.now() - started) * 100) / 100,
        response,
      })
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : t('workflow.detail.callConfig.playground.errors.requestFailed'))
    } finally {
      setRunning(false)
    }
  }

  const handleSseRequest = async () => {
    const inputs = parseInputs()
    if (!inputs) return
    abortController.current?.abort()
    const controller = new AbortController()
    abortController.current = controller
    setRunning(true)
    setError(null)
    setStreamEvents([])
    try {
      for await (const event of streamWorkflowExecution(workflowId, inputs, { signal: controller.signal })) {
        if (!event) continue
        setStreamEvents((current) => [
          ...current,
          { event: event.event || 'message', data: parseEventData(event.data) },
        ])
      }
    } catch (requestError) {
      if (!controller.signal.aborted) {
        setError(requestError instanceof Error ? requestError.message : t('workflow.detail.callConfig.playground.errors.requestFailed'))
      }
    } finally {
      if (abortController.current === controller) abortController.current = null
      setRunning(false)
    }
  }

  const stopStream = () => {
    abortController.current?.abort()
    abortController.current = null
    setRunning(false)
  }

  const reset = () => {
    stopStream()
    setInputsText(DEFAULT_INPUTS)
    setError(null)
    setHttpResult(null)
    setStreamEvents([])
  }

  const close = () => {
    stopStream()
    onClose()
  }

  const copy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value)
      toast.success(t('workflow.detail.callConfig.playground.toast.copied'))
    } catch {
      toast.error(t('workflow.detail.callConfig.playground.toast.copyFailed'))
    }
  }

  return (
    <Dialog open={visible} onOpenChange={(open) => !open && close()}>
      <DialogContent className="max-h-[92vh] gap-0 p-0 sm:max-w-4xl">
        <DialogHeader className="border-b p-6">
          <DialogTitle>{t('workflow.detail.callConfig.playground.title')}</DialogTitle>
          <DialogDescription>
            {t('workflow.detail.callConfig.playground.description', { name: workflowName })}
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="max-h-[calc(92vh-9rem)]">
          <div className="space-y-6 p-6">
            <Tabs value={mode} onValueChange={(value) => setMode(value as PlaygroundMode)}>
              <TabsList className="grid w-full max-w-sm grid-cols-2">
                <TabsTrigger value="http"><Send className="mr-2 size-4" />HTTP</TabsTrigger>
                <TabsTrigger value="sse"><Radio className="mr-2 size-4" />SSE</TabsTrigger>
              </TabsList>

              <TabsContent value="http" className="mt-4 text-sm text-muted-foreground">
                {t('workflow.detail.callConfig.playground.modes.httpDescription')}
              </TabsContent>
              <TabsContent value="sse" className="mt-4 text-sm text-muted-foreground">
                {t('workflow.detail.callConfig.playground.modes.sseDescription')}
              </TabsContent>
            </Tabs>

            <section className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <Label>{t('workflow.detail.callConfig.playground.endpoint')}</Label>
                <Button variant="ghost" size="sm" onClick={() => void copy(endpoint)}>
                  <Copy className="mr-2 size-4" />
                  {t('workflow.detail.callConfig.playground.actions.copy')}
                </Button>
              </div>
              <code className="block overflow-x-auto rounded-lg border bg-muted/50 p-3 text-xs">{endpoint}</code>
              <p className="text-xs text-muted-foreground">{t('workflow.detail.callConfig.playground.authHint')}</p>
            </section>

            <section className="space-y-2">
              <Label htmlFor="workflow-playground-inputs">{t('workflow.detail.callConfig.playground.inputs')}</Label>
              <Textarea
                id="workflow-playground-inputs"
                className="min-h-40 font-mono text-sm"
                value={inputsText}
                spellCheck={false}
                onChange={(event) => setInputsText(event.target.value)}
              />
            </section>

            <div className="flex flex-wrap gap-2">
              {mode === 'http' ? (
                <Button onClick={() => void handleHttpRequest()} disabled={running}>
                  <Play className="mr-2 size-4" />
                  {running
                    ? t('workflow.detail.callConfig.playground.actions.sending')
                    : t('workflow.detail.callConfig.playground.actions.sendHttp')}
                </Button>
              ) : running ? (
                <Button variant="destructive" onClick={stopStream}>
                  <Square className="mr-2 size-4" />
                  {t('workflow.detail.callConfig.playground.actions.stopSse')}
                </Button>
              ) : (
                <Button onClick={() => void handleSseRequest()}>
                  <Radio className="mr-2 size-4" />
                  {t('workflow.detail.callConfig.playground.actions.startSse')}
                </Button>
              )}
              <Button variant="outline" onClick={reset}>
                <RotateCcw className="mr-2 size-4" />
                {t('workflow.detail.callConfig.playground.actions.reset')}
              </Button>
            </div>

            {error && (
              <div role="alert" className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
                {error}
              </div>
            )}

            {mode === 'http' && httpResult !== null && (
              <section className="space-y-2">
                <h3 className="font-semibold">{t('workflow.detail.callConfig.playground.httpResult')}</h3>
                <pre className="max-h-72 overflow-auto rounded-lg border bg-muted/50 p-4 text-xs">
                  {JSON.stringify(httpResult, null, 2)}
                </pre>
              </section>
            )}

            {mode === 'sse' && (
              <section className="space-y-2">
                <h3 className="font-semibold">{t('workflow.detail.callConfig.playground.sseEvents')}</h3>
                {streamEvents.length ? (
                  <div className="space-y-2">
                    {streamEvents.map((event, index) => (
                      <div key={`${event.event}:${index}`} className="rounded-lg border p-3">
                        <Badge variant={event.event === 'error' ? 'destructive' : 'outline'}>{event.event}</Badge>
                        <pre className="mt-2 overflow-x-auto text-xs">{JSON.stringify(event.data, null, 2)}</pre>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">{t('workflow.detail.callConfig.playground.emptyEvents')}</p>
                )}
              </section>
            )}

            <section className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <h3 className="font-semibold">{t('workflow.detail.callConfig.playground.curlSample')}</h3>
                <Button variant="ghost" size="sm" onClick={() => void copy(sample)}>
                  <Copy className="mr-2 size-4" />
                  {t('workflow.detail.callConfig.playground.actions.copy')}
                </Button>
              </div>
              <pre className="overflow-x-auto rounded-lg border bg-muted/50 p-4 text-xs">{sample}</pre>
            </section>
          </div>
        </ScrollArea>

        <DialogFooter className="border-t p-4">
          <Button variant="outline" onClick={close}>{t('workflow.detail.callConfig.playground.actions.close')}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
