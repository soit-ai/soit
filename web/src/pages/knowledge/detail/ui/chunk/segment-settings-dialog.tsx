import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import type { SegmentConfig } from './types'

interface SegmentSettingsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  config: SegmentConfig
  onConfigChange: (config: SegmentConfig) => void
  onSave: () => void
}

export function SegmentSettingsDialog({
  open,
  onOpenChange,
  config,
  onConfigChange,
  onSave,
}: SegmentSettingsDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Chunk Settings</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="space-y-4">
            <h4 className="font-medium">Parent Chunk</h4>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="parentIdentifier" className="text-right">
                Separator
              </Label>
              <Input
                id="parentIdentifier"
                value={config.parent.separator}
                onChange={e => onConfigChange({
                  ...config,
                  parent: { ...config.parent, separator: e.target.value }
                })}
                className="col-span-3"
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="parentMaxLength" className="text-right">
                Max Length
              </Label>
              <Input
                id="parentMaxLength"
                type="number"
                value={config.parent.maxLength}
                onChange={e => onConfigChange({
                  ...config,
                  parent: { ...config.parent, maxLength: parseInt(e.target.value) }
                })}
                className="col-span-3"
              />
            </div>
          </div>
          <div className="space-y-4">
            <h4 className="font-medium">Child Chunk</h4>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="childIdentifier" className="text-right">
                Separator
              </Label>
              <Input
                id="childIdentifier"
                value={config.child.separator}
                onChange={e => onConfigChange({
                  ...config,
                  child: { ...config.child, separator: e.target.value }
                })}
                className="col-span-3"
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="childMaxLength" className="text-right">
                Max Length
              </Label>
              <Input
                id="childMaxLength"
                type="number"
                value={config.child.maxLength}
                onChange={e => onConfigChange({
                  ...config,
                  child: { ...config.child, maxLength: parseInt(e.target.value) }
                })}
                className="col-span-3"
              />
            </div>
          </div>
          <div className="space-y-4">
            <h4 className="font-medium">Preprocessing</h4>
            <div className="flex items-center justify-between">
              <Label htmlFor="replaceWhitespace">Replace Whitespace</Label>
              <Switch
                id="replaceWhitespace"
                checked={config.preprocess.replaceWhitespace}
                onCheckedChange={checked => onConfigChange({
                  ...config,
                  preprocess: { ...config.preprocess, replaceWhitespace: checked }
                })}
              />
            </div>
            <div className="flex items-center justify-between">
              <Label htmlFor="removeUrls">Remove URLs</Label>
              <Switch
                id="removeUrls"
                checked={config.preprocess.removeUrl}
                onCheckedChange={checked => onConfigChange({
                  ...config,
                  preprocess: { ...config.preprocess, removeUrl: checked }
                })}
              />
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={onSave}>
            Save
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
} 