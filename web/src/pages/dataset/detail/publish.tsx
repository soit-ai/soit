import { useEffect, useState } from 'react'
import { useParams } from 'react-router'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { getDataset, updateDataset, type Dataset } from '@/services/dataset-service'
import { toast } from 'sonner'
import { useTranslation } from '@/i18n'

function Page() {
  const { t } = useTranslation()
  const { datasetId } = useParams<{ datasetId: string }>()
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [loading, setLoading] = useState(false)

  const fetchDataset = async () => {
    if (!datasetId) return
    try {
      setLoading(true)
      const data = await getDataset(datasetId)
      setDataset(data)
    } catch (error) {
      toast.error(t('dataset.publish.toast.fetchError'))
      console.error('Failed to fetch dataset:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDataset()
  }, [datasetId])

  const handleCopy = async () => {
    if (!datasetId) return
    try {
      await navigator.clipboard.writeText(datasetId)
      toast.success(t('dataset.publish.toast.copySuccess'))
    } catch (error) {
      toast.error(t('dataset.publish.toast.copyError'))
      console.error('Failed to copy dataset id:', error)
    }
  }

  const toggleVisibility = async () => {
    if (!datasetId || !dataset) return
    const nextVisibility = dataset.visibility === 'private' ? 'workspace' : 'private'
    try {
      setLoading(true)
      const updated = await updateDataset(datasetId, { visibility: nextVisibility })
      setDataset(updated)
      toast.success(t('dataset.publish.toast.visibilityUpdated'))
    } catch (error) {
      toast.error(t('dataset.publish.toast.visibilityError'))
      console.error('Failed to update visibility:', error)
    } finally {
      setLoading(false)
    }
  }

  const visibilityLabel = dataset?.visibility
    ? t(`dataset.visibility.${dataset.visibility}`)
    : '-'

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <Card>
        <CardHeader>
          <CardTitle>{t('dataset.publish.title')}</CardTitle>
          <CardDescription>{t('dataset.publish.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-2">
            <div className="text-sm font-medium">{t('dataset.publish.fields.datasetId')}</div>
            <div className="flex items-center gap-2">
              <Input value={datasetId || ''} readOnly />
              <Button variant="outline" onClick={handleCopy} disabled={!datasetId}>
                {t('dataset.publish.actions.copy')}
              </Button>
            </div>
          </div>
          <div className="grid gap-2">
            <div className="text-sm font-medium">{t('dataset.publish.fields.visibility')}</div>
            <div className="flex items-center gap-2">
              <Input value={visibilityLabel} readOnly />
              <Button variant="outline" onClick={toggleVisibility} disabled={loading || !dataset}>
                {t('dataset.publish.actions.toggle')}
              </Button>
            </div>
          </div>
          <div className="text-xs text-muted-foreground">
            {t('dataset.publish.notice')}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default Page
