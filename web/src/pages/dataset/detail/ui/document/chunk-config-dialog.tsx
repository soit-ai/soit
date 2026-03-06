import { useTranslation } from '@/i18n'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useState } from 'react'

interface ChunkConfig {
  chunk_size: number
  chunk_overlap: number
  separator: string
}

interface ChunkConfigDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  config: ChunkConfig
  onConfigChange: (config: ChunkConfig) => void
}

export function ChunkConfigDialog({ open, onOpenChange, config, onConfigChange }: ChunkConfigDialogProps) {
  const { t } = useTranslation()
  const [localConfig, setLocalConfig] = useState<ChunkConfig>(config)

  const handleSave = () => {
    onConfigChange(localConfig)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('dataset.document.chunk.config.title')}</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="chunk_size" className="text-right">
              {t('dataset.document.chunk.config.chunk_size')}
            </Label>
            <Input
              id="chunk_size"
              type="number"
              value={localConfig.chunk_size}
              onChange={(e) => setLocalConfig({ ...localConfig, chunk_size: parseInt(e.target.value) })}
              className="col-span-3"
            />
          </div>
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="chunk_overlap" className="text-right">
              {t('dataset.document.chunk.config.chunk_overlap')}
            </Label>
            <Input
              id="chunk_overlap"
              type="number"
              value={localConfig.chunk_overlap}
              onChange={(e) => setLocalConfig({ ...localConfig, chunk_overlap: parseInt(e.target.value) })}
              className="col-span-3"
            />
          </div>
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="separator" className="text-right">
              {t('dataset.document.chunk.config.separator')}
            </Label>
            <Input
              id="separator"
              value={localConfig.separator}
              onChange={(e) => setLocalConfig({ ...localConfig, separator: e.target.value })}
              className="col-span-3"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t('dataset.document.chunk.config.cancel')}
          </Button>
          <Button onClick={handleSave}>{t('dataset.document.chunk.config.save')}</Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// Named export is used; default export is not needed.
