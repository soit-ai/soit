import { useEffect, useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { downloadKnowledgeDocument, getKnowledgeDocumentContent } from '@/services/knowledge-service'
import { toast } from 'sonner'
import { useTranslation } from '@/i18n'

const DocumentType = {
  TEXT: 'text',
  IMAGE: 'image',
  VIDEO: 'video',
  LINK: 'link',
  WEBSITE: 'website',
} as const

interface DocumentPreviewDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  knowledgeId: string
  document: {
    id: string
    name: string
    type: string
    content?: string
    mime_type?: string | null
  } | null
}

export function DocumentPreviewDialog({
  open,
  onOpenChange,
  knowledgeId,
  document
}: DocumentPreviewDialogProps) {
  const { t } = useTranslation()
  const [content, setContent] = useState<string | null>(null)
  const [objectUrl, setObjectUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open || !document) return
    let active = true
    const loadContent = async () => {
      setLoading(true)
      setContent(null)
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl)
        setObjectUrl(null)
      }

      try {
        if (document.type === DocumentType.WEBSITE && document.content) {
          setObjectUrl(document.content)
          return
        }

        const mimeType = document.mime_type || ''
        const isBinary = mimeType.startsWith('image/') || mimeType.startsWith('video/') || mimeType === 'application/pdf'

        if (isBinary) {
          const response = await downloadKnowledgeDocument(knowledgeId, document.id)
          const blob = response.data as Blob
          const url = URL.createObjectURL(blob)
          if (active) {
            setObjectUrl(url)
          } else {
            URL.revokeObjectURL(url)
          }
        } else {
          const text = await getKnowledgeDocumentContent(knowledgeId, document.id)
          if (active) {
            setContent(text)
          }
        }
      } catch (error) {
        toast.error(t('knowledge.document.preview.fetchError'))
        console.error('Failed to load document content:', error)
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    loadContent()
    return () => {
      active = false
    }
  }, [open, document?.id, knowledgeId])

  useEffect(() => {
    if (!open && objectUrl && !objectUrl.startsWith('http')) {
      URL.revokeObjectURL(objectUrl)
      setObjectUrl(null)
    }
  }, [open, objectUrl])

  const renderPreviewContent = () => {
    if (loading) {
      return <div>{t('knowledge.document.preview.loading')}</div>
    }
    if (document?.type === DocumentType.WEBSITE && objectUrl) {
      return <iframe src={objectUrl} className="w-full h-[500px]" />
    }
    const mimeType = document?.mime_type || ''
    if (mimeType.startsWith('image/') && objectUrl) {
      return <img src={objectUrl} alt={document?.name} className="max-w-full h-auto" />
    }
    if (mimeType.startsWith('video/') && objectUrl) {
      return <video src={objectUrl} controls className="max-w-full" />
    }
    if (mimeType === 'application/pdf' && objectUrl) {
      return <iframe src={objectUrl} className="w-full h-[500px]" />
    }
    if (content) {
      return <div className="whitespace-pre-wrap">{content}</div>
    }
    return <div>{t('knowledge.document.preview.unavailable')}</div>
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>{document?.name}</DialogTitle>
        </DialogHeader>
        <div className="mt-4">
          {document && renderPreviewContent()}
        </div>
      </DialogContent>
    </Dialog>
  )
}

