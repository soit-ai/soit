import { Drawer, DrawerContent, DrawerHeader, DrawerTitle, DrawerDescription, DrawerFooter, DrawerClose } from '@/components/ui/drawer'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import type { Chunk } from './types'

interface ChunkEditDrawerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  chunk: Chunk | null
  content: string
  switchValue: boolean
  tags: string[]
  newTag: string
  onContentChange: (content: string) => void
  onSwitchChange: (value: boolean) => void
  onTagsChange: (tags: string[]) => void
  onNewTagChange: (tag: string) => void
  onSave: () => void
  onDelete: () => void
}

export function ChunkEditDrawer({
  open,
  onOpenChange,
  chunk,
  content,
  switchValue,
  tags,
  newTag,
  onContentChange,
  onSwitchChange,
  onTagsChange,
  onNewTagChange,
  onSave,
  onDelete,
}: ChunkEditDrawerProps) {
  return (
    <Drawer open={open} direction="right" onOpenChange={onOpenChange}>
      <DrawerContent className="w-[500px] max-w-full flex flex-col h-full">
        <DrawerHeader className="border-b pb-4">
          <DrawerTitle className="text-2xl font-bold mb-2">Edit Chunk</DrawerTitle>
          <DrawerDescription className="text-sm text-muted-foreground">Edit chunk content, toggle status, manage tags</DrawerDescription>
          <div className="text-xs text-muted-foreground mt-2">ID: {chunk?.id}</div>
        </DrawerHeader>
        <div className="flex-1 overflow-y-auto p-6 space-y-8">
          <div className="space-y-2">
            <label className="text-sm font-medium">Content</label>
            <Textarea
              value={content}
              onChange={e => onContentChange(e.target.value)}
              className="h-40 resize-none"
            />
          </div>
          <div className="flex items-center justify-between p-4 bg-muted/50 rounded-lg">
            <label className="font-medium">Switch</label>
            <Switch
              checked={switchValue}
              onCheckedChange={onSwitchChange}
            />
          </div>
          <div className="space-y-4">
            <label className="text-sm font-medium">Tags</label>
            <div className="flex gap-2 flex-wrap min-h-[32px] p-2 bg-muted/30 rounded-lg">
              {tags.map((tag, idx) => (
                <Badge key={idx} variant="secondary" className="flex items-center gap-1 px-2 py-1">
                  {tag}
                  <button
                    className="ml-1 text-xs text-destructive hover:text-destructive/80 transition-colors"
                    onClick={() => onTagsChange(tags.filter((_, i) => i !== idx))}
                    type="button"
                  >×</button>
                </Badge>
              ))}
            </div>
            <div className="flex gap-2">
              <Input
                value={newTag}
                onChange={e => onNewTagChange(e.target.value)}
                placeholder="Add tag"
                className="flex-1"
                onKeyDown={e => {
                  if (e.key === 'Enter' && newTag.trim()) {
                    onTagsChange([...tags, newTag.trim()])
                    onNewTagChange('')
                  }
                }}
              />
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  if (newTag.trim()) {
                    onTagsChange([...tags, newTag.trim()])
                    onNewTagChange('')
                  }
                }}
              >Add</Button>
            </div>
          </div>
        </div>
        <DrawerFooter className="border-t p-6 gap-4">
          <div className="flex gap-3 justify-end">
            <DrawerClose asChild>
              <Button variant="outline">Cancel</Button>
            </DrawerClose>
            <Button
              variant="destructive"
              onClick={onDelete}
            >Delete</Button>
            <Button onClick={onSave}>Save</Button>
          </div>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  )
} 