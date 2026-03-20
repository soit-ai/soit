import { useState } from 'react'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { Upload, XCircle } from 'lucide-react'
import { uploadKnowledgeDocument } from '@/services/knowledge-service'
import { toast } from 'sonner'
import { useTranslation } from '@/i18n'

export interface UploadDocumentDialogProps {
  knowledgeId: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onUploadSuccess?: () => void
}

export function UploadDocumentDialog({
  knowledgeId,
  open,
  onOpenChange,
  onUploadSuccess
}: UploadDocumentDialogProps) {
  const { t } = useTranslation()
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setSelectedFiles(Array.from(e.target.files))
    }
  }

  const handleUpload = async () => {
    if (selectedFiles.length === 0) return

    setUploading(true)
    try {
      for (let i = 0; i < selectedFiles.length; i++) {
        const file = selectedFiles[i]
        const progress = Math.round(((i + 1) / selectedFiles.length) * 100)
        setUploadProgress(progress)
        const docKey = `${Date.now()}-${file.name}`
        await uploadKnowledgeDocument(
          knowledgeId,
          {
            doc_key: docKey,
            source_type: 'upload',
            title: file.name,
            filename: file.name,
            mime_type: file.type,
            size_bytes: file.size,
          },
          file
        )
      }
      toast.success(t('knowledge.document.upload.toast.success'))
      onOpenChange(false)
      onUploadSuccess?.()
    } catch (error) {
      toast.error(t('knowledge.document.upload.toast.error'))
      console.error('Upload error:', error)
    } finally {
      setUploading(false)
      setUploadProgress(0)
      setSelectedFiles([])
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t('knowledge.document.common.upload')}</DialogTitle>
          <DialogDescription>
            {t('knowledge.document.upload.description')}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="border-2 border-dashed rounded-lg p-8 text-center">
            <input
              type="file"
              multiple
              onChange={handleFileSelect}
              className="hidden"
              id="file-upload"
              accept=".txt,.pdf,.doc,.docx,.md,.html,.htm"
            />
            <label
              htmlFor="file-upload"
              className="cursor-pointer flex flex-col items-center gap-2"
            >
              <Upload className="h-8 w-8 text-muted-foreground" />
              <div className="text-sm font-medium">
                {t('knowledge.document.upload.dropzone.title')}
              </div>
              <div className="text-xs text-muted-foreground">
                {t('knowledge.document.upload.dropzone.subtitle')}
              </div>
            </label>
          </div>
          {selectedFiles.length > 0 && (
            <div className="space-y-2">
              <div className="text-sm font-medium">
                {t('knowledge.document.upload.selectedFiles', { count: selectedFiles.length })}
              </div>
              <div className="space-y-2">
                {selectedFiles.map((file, index) => (
                  <div key={index} className="flex items-center justify-between p-2 rounded-lg border">
                    <div className="flex items-center gap-2">
                      <span className="text-sm">{file.name}</span>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setSelectedFiles(files => files.filter((_, i) => i !== index))}
                    >
                      <XCircle className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        {uploading && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span>{t('knowledge.document.upload.progress')}</span>
              <span>{uploadProgress}%</span>
            </div>
            <Progress value={uploadProgress} />
          </div>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t('knowledge.document.upload.actions.cancel')}
          </Button>
          <Button
            onClick={handleUpload}
            disabled={uploading || selectedFiles.length === 0}
          >
            {uploading ? t('knowledge.document.upload.actions.processing') : t('knowledge.document.upload.actions.confirm')}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

