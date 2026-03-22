import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { useTranslation } from '@/i18n'

interface SegmentConfig {
  parent: {
    separator: string
    maxLength: number
  }
  child: {
    separator: string
    maxLength: number
  }
  preprocess: {
    replaceWhitespace: boolean
    removeUrl: boolean
  }
}

interface SegmentSettingsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  config: SegmentConfig
  onConfigChange: (config: SegmentConfig) => void
}

export function SegmentSettingsDialog({
  open,
  onOpenChange,
  config,
  onConfigChange
}: SegmentSettingsDialogProps) {
  const { t } = useTranslation()

  const handleSave = () => {
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('knowledge.document.segment.title')}</DialogTitle>
        </DialogHeader>
        <div className="space-y-6">
          <div>
            <div className="font-medium mb-2">{t('knowledge.document.segment.parent.title')}</div>
            <div className="space-y-2 border rounded-lg p-4">
              <div className="flex items-center gap-4">
                <Label className="w-24">{t('knowledge.document.segment.fields.separator')}</Label>
                <Input 
                  value={config.parent.separator} 
                  onChange={e => onConfigChange({
                    ...config,
                    parent: {
                      ...config.parent,
                      separator: e.target.value
                    }
                  })} 
                  className="w-32" 
                />
                <Label className="w-28 text-right">{t('knowledge.document.segment.fields.maxLength')}</Label>
                <Input 
                  type="number" 
                  value={config.parent.maxLength} 
                  onChange={e => onConfigChange({
                    ...config,
                    parent: {
                      ...config.parent,
                      maxLength: Number(e.target.value)
                    }
                  })} 
                  className="w-24" 
                />
                <span className="text-xs text-muted-foreground">{t('knowledge.document.segment.units.characters')}</span>
              </div>
            </div>
          </div>
          <div>
            <div className="font-medium mb-2">{t('knowledge.document.segment.child.title')}</div>
            <div className="space-y-2 border rounded-lg p-4">
              <div className="flex items-center gap-4">
                <Label className="w-24">{t('knowledge.document.segment.fields.separator')}</Label>
                <Input 
                  value={config.child.separator} 
                  onChange={e => onConfigChange({
                    ...config,
                    child: {
                      ...config.child,
                      separator: e.target.value
                    }
                  })} 
                  className="w-32" 
                />
                <Label className="w-28 text-right">{t('knowledge.document.segment.fields.maxLength')}</Label>
                <Input 
                  type="number" 
                  value={config.child.maxLength} 
                  onChange={e => onConfigChange({
                    ...config,
                    child: {
                      ...config.child,
                      maxLength: Number(e.target.value)
                    }
                  })} 
                  className="w-24" 
                />
                <span className="text-xs text-muted-foreground">{t('knowledge.document.segment.units.characters')}</span>
              </div>
            </div>
          </div>
          <div>
            <div className="font-medium mb-2">{t('knowledge.document.segment.preprocess.title')}</div>
            <div className="space-y-2 border rounded-lg p-4">
              <div className="flex items-center gap-4">
                <Switch 
                  checked={config.preprocess.replaceWhitespace} 
                  onCheckedChange={v => onConfigChange({
                    ...config,
                    preprocess: {
                      ...config.preprocess,
                      replaceWhitespace: v
                    }
                  })} 
                />
                <span>{t('knowledge.document.segment.preprocess.replaceWhitespace')}</span>
              </div>
              <div className="flex items-center gap-4">
                <Switch 
                  checked={config.preprocess.removeUrl} 
                  onCheckedChange={v => onConfigChange({
                    ...config,
                    preprocess: {
                      ...config.preprocess,
                      removeUrl: v
                    }
                  })} 
                />
                <span>{t('knowledge.document.segment.preprocess.removeUrl')}</span>
              </div>
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <Button variant="outline" onClick={() => onOpenChange(false)}>{t('knowledge.document.segment.actions.cancel')}</Button>
          <Button onClick={handleSave}>{t('knowledge.document.segment.actions.save')}</Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
