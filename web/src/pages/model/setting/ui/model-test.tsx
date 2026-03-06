import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { useToast } from '@/hooks/use-toast'
import { Loader2 } from 'lucide-react'
import { useTranslation } from '@/i18n'
import { testModelConnection } from '@/services/provider-service'

interface ModelTestProps {
  providerId: string
  modelId: string
  modelName: string
}

export function ModelTest({ providerId, modelId, modelName }: ModelTestProps) {
  const { t } = useTranslation()
  const { toast } = useToast()
  const [loading, setLoading] = useState(false)
  const [testInput, setTestInput] = useState('')
  const [testResult, setTestResult] = useState<{
    success: boolean
    message: string
    response?: string
    latency?: number
  } | null>(null)

  const handleTest = async () => {
    if (!testInput.trim()) {
      toast({
        title: t('system.model.test.failure'),
        description: t('system.model.test.inputPlaceholder'),
        type: 'error',
      })
      return
    }
    setLoading(true)
    try {
      const result = await testModelConnection(providerId, modelId, testInput, 'chat')
      setTestResult({
        success: result.success,
        message: result.message,
        response: result.response,
        latency: result.latency_ms,
      })
    } catch (error: any) {
      setTestResult({
        success: false,
        message: error?.message || 'Test failed',
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('system.model.test.title')}</CardTitle>
        <CardDescription>
          {t('system.model.test.description', { modelName })}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="test-input">{t('system.model.test.inputLabel')}</Label>
          <Textarea
            id="test-input"
            placeholder={t('system.model.test.inputPlaceholder')}
            value={testInput}
            onChange={(e) => setTestInput(e.target.value)}
            rows={4}
          />
        </div>

        {testResult && (
          <div className="space-y-2">
            <Label>{t('system.model.test.resultLabel')}</Label>
            <div className={`p-4 rounded-md ${testResult.success ? 'bg-green-50' : 'bg-red-50'}`}>
              <div className="font-medium">
                {testResult.success ? t('system.model.test.success') : t('system.model.test.failure')}
              </div>
              <div className="text-sm text-muted-foreground mt-1">
                {testResult.message}
              </div>
              {testResult.response && (
                <div className="mt-2 p-2 bg-background rounded border">
                  <div className="text-sm font-medium mb-1">{t('system.model.test.responseLabel')}</div>
                  <div className="text-sm whitespace-pre-wrap">{testResult.response}</div>
                </div>
              )}
              {testResult.latency && (
                <div className="text-sm text-muted-foreground mt-2">
                  {t('system.model.test.latencyLabel', { latency: testResult.latency })}
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
      <CardFooter>
        <Button
          onClick={handleTest}
          disabled={loading}
          className="w-full"
        >
          {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
          {t('system.model.test.start')}
        </Button>
      </CardFooter>
    </Card>
  )
} 
